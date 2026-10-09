import csv
import datetime as dt
import json
import os
import re

from . import audit, drafts, scoring
from .filters import RoleRules, anonymous_employer, is_blocked, is_public_sector, load_blocklist, norm_name


def _blank_lead(company, city, state, source):
    return {"source": source, "company": company, "website": "", "phone": "", "city": city, "state": state,
            "vertical": "", "emp": None, "hiring": "N", "expand": "N", "detail": "", "sigdate": None, "first": "",
            "last": "", "title": "", "email": "", "linkedin": "", "psi": None, "outdated": "", "estatus": "Unverified",
            "status": "New", "n_postings": 0, "titles": [], "urls": [], "audit_note": ""}


def _employees(text):
    """'51 to 200' / '51-200' / '120' -> midpoint int; None if unreadable."""
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text or "")]
    return sum(nums[:2]) // len(nums[:2]) if nums else None


def load_enrichment(path):
    """CSV from Hunter/Apollo/Places/Indeed profiles, etc. Columns: company,website,employees,phone,first,last,title,
    email,linkedin,estatus. Matched to leads by company name."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[norm_name(r["company"])] = r
    return out


class Engine:
    def __init__(self, query, cfg, batches, seen_path=None, do_audit=False, blocklist_path=None, today=None,
                 enrichment=None):
        self.q, self.cfg, self.batches = query, cfg, iter(batches)
        self.rules = RoleRules(query.get("professions", []))
        self.block = load_blocklist(blocklist_path)
        self.today = today or dt.date.today()
        self.do_audit, self.pool, self.exhausted = do_audit, {}, False
        self.enrichment = enrichment or {}
        self.seen_path = seen_path
        self.seen = set(json.load(open(seen_path))) if seen_path and os.path.exists(seen_path) else set()
        self.stats = {"scanned": 0, "enterprise_or_staffing": 0, "anonymous": 0, "part_time": 0, "irrelevant_role": 0,
                      "already_delivered": 0}

    # ---- ingest -------------------------------------------------------
    def _ingest(self, cand):
        self.stats["scanned"] += 1
        name = cand["company"]
        if anonymous_employer(name):
            self.stats["anonymous"] += 1
            return
        if is_blocked(name, self.block) or is_public_sector(name):
            self.stats["enterprise_or_staffing"] += 1
            return
        city, state = cand["city_label"].rsplit(", ", 1)
        if cand["kind"] == "posting":
            if cand["job_type"] in self.cfg["excluded_job_types"]:
                self.stats["part_time"] += 1
                return
            if not self.rules.relevant(cand["title"]):
                self.stats["irrelevant_role"] += 1
                return
        key = f"{norm_name(name)}|{city.lower()}"
        lead = self.pool.get(key) or self.pool.setdefault(key, _blank_lead(name, city, state, "Indeed" if cand["kind"] == "posting" else "Google Maps"))
        if self.q.get("industry"):
            lead["vertical"] = lead["vertical"] or self.q["industry"]
        if cand["kind"] == "posting":
            lead["hiring"] = "Y"
            lead["n_postings"] += 1
            if cand["title"] not in lead["titles"]:
                lead["titles"].append(cand["title"])
            if cand["url"]:
                lead["urls"].append(cand["url"])
            if cand["posted"] and (not lead["sigdate"] or cand["posted"] > lead["sigdate"]):
                lead["sigdate"] = cand["posted"]
            lead["detail"] = "; ".join(lead["titles"][:2])
        else:
            lead["website"] = lead["website"] or cand.get("website", "")
            lead["phone"] = lead["phone"] or cand.get("phone", "")

    def _enrich(self, lead):
        row = self.enrichment.get(norm_name(lead["company"]))
        if row:
            for k, col in (("website", "website"), ("phone", "phone"), ("first", "first"), ("last", "last"),
                           ("title", "title"), ("email", "email"), ("linkedin", "linkedin")):
                if row.get(col) and not lead[k]:
                    lead[k] = row[col].strip()
            if row.get("employees") and lead["emp"] is None:
                lead["emp"] = _employees(row["employees"])
            if row.get("estatus"):
                lead["estatus"] = row["estatus"].strip()
        if self.do_audit and lead["website"] and not lead["outdated"]:
            r = audit.audit_site(lead["website"])
            lead["outdated"], lead["audit_note"] = r["outdated"], r["note"]
            key = os.environ.get("PAGESPEED_API_KEY")
            if key and lead["psi"] is None:
                lead["psi"] = audit.psi_score(lead["website"], key)

    # ---- scoring / selection ------------------------------------------
    def _finish(self, lead):
        lead.update(scoring.score(lead, self.cfg, [self.q["industry"]] if self.q.get("industry") else (), self.today))
        lead["tier"] = scoring.tier(lead, self.cfg, self.today)
        lead["why"] = scoring.why(lead)
        lead["signal"], lead["subject"], lead["body"] = drafts.draft(lead, self.cfg)
        lead["notes"] = " | ".join(lead["urls"])
        need = [n for n, missing in (("website", not lead["website"]), ("decision-maker email", not lead["email"]),
                                     ("phone", not lead["phone"]), ("employee count", lead["emp"] is None)) if missing]
        lead["next_step"] = ("Find " + ", ".join(need)) if need else "Verify email, then review draft"

    def _ready(self):
        want = {"hot": {"hot"}, "warm": {"hot", "warm"}, "any": {"hot", "warm", "cold"}}[self.q.get("interest", "warm")]
        out = []
        for key, lead in self.pool.items():
            if key in self.seen:
                continue
            self._finish(lead)
            if lead["tier"] in want:
                out.append((key, lead))
        out.sort(key=lambda kv: (-kv[1]["total"], -kv[1]["n_postings"],
                                 -(kv[1]["sigdate"].toordinal() if kv[1]["sigdate"] else 0), kv[1]["company"].lower()))
        return out

    def fill(self, target):
        """Pull batches until `target` fresh leads qualify or sources run dry."""
        while len(self._ready()) < target and not self.exhausted:
            try:
                batch = next(self.batches)
            except StopIteration:
                self.exhausted = True
                break
            for cand in batch:
                self._ingest(cand)
            for lead in self.pool.values():
                self._enrich(lead)

    def take(self, target):
        ready = self._ready()[:target]
        for key, _ in ready:
            self.seen.add(key)
        if self.seen_path:
            os.makedirs(os.path.dirname(self.seen_path) or ".", exist_ok=True)
            json.dump(sorted(self.seen), open(self.seen_path, "w"))
        return [lead for _, lead in ready]
