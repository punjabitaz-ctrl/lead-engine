import csv
import datetime as dt
import json
import os
import re

from . import audit, drafts, packs, presence, scoring
from .filters import RoleRules, anonymous_employer, is_blocked, is_health_system, is_public_sector, load_blocklist, norm_name


def _blank_lead(company, city, state, source):
    return {"source": source, "company": company, "website": "", "phone": "", "city": city, "state": state,
            "vertical": "", "emp": None, "hiring": "N", "expand": "N", "detail": "", "sigdate": None, "first": "",
            "last": "", "title": "", "email": "", "linkedin": "", "psi": None, "outdated": "", "estatus": "Unverified",
            "status": "New", "n_postings": 0, "titles": [], "urls": [], "audit_note": "", "specialty": "", "npi": "",
            "hasweb": "", "hasgbp": "", "reviews": None, "address": "", "provider": False, "priority": 9, "providers": None, "sizeov": "",
            "country": "", "locations": None}


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
                 enrichment=None, presence_data=None, checker=None, priority_first=False, group_by_specialty=False,
                 pack=None, contact_finder=None):
        self.q, self.cfg, self.batches = query, cfg, iter(batches)
        self.rules = RoleRules(query.get("professions", []), rules=packs.role_rules(pack))
        self.ownership = packs.ownership_patterns(pack)
        self.templates = packs.templates(pack)
        self.contact_finder = contact_finder
        self.block = load_blocklist(blocklist_path)
        self.today = today or dt.date.today()
        self.do_audit, self.pool, self.exhausted = do_audit, {}, False
        self.enrichment = enrichment or {}
        self.priority_first = priority_first
        self.group_by_specialty = group_by_specialty
        self.presence_data, self.checker = presence_data or {}, checker
        self.seen_path = seen_path
        self.seen = set()
        if seen_path and os.path.exists(seen_path):
            with open(seen_path, encoding="utf-8") as fh:
                self.seen = set(json.load(fh))
        self.stats = {"scanned": 0, "enterprise_or_staffing": 0, "anonymous": 0, "part_time": 0, "irrelevant_role": 0,
                      "already_delivered": 0, "not_private": 0}

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
        if any(p.search(name) for p in self.ownership):
            self.stats["not_private"] += 1
            return
        city, state = cand["city_label"].rsplit(", ", 1)
        if cand["kind"] == "provider":
            if is_health_system(name) or (cand["npi_type"] == "NPI-1" and cand["sole"] != "YES"):
                self.stats["not_private"] += 1
                return
        if cand["kind"] == "posting":
            if cand["job_type"] in self.cfg["excluded_job_types"]:
                self.stats["part_time"] += 1
                return
            if not self.rules.relevant(cand["title"]):
                self.stats["irrelevant_role"] += 1
                return
        key = f"{norm_name(name)}|{city.lower()}"
        src = cand.get("origin") or {"posting": "Indeed", "business": "Google Maps", "provider": "NPPES", "company": "Company list"}[cand["kind"]]
        lead = self.pool.get(key) or self.pool.setdefault(key, _blank_lead(name, city, state, src))
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
        elif cand["kind"] == "provider":
            lead["provider"] = True
            lead["providers"] = cand.get("providers", lead["providers"])
            lead["sizeov"] = cand.get("size_override", lead["sizeov"])
            lead["priority"] = cand.get("priority", 9)
            if cand.get("evidence"):
                lead["detail"] = cand["evidence"]
            if cand.get("origin_note"):
                lead["urls"].append("Source: " + cand["origin_note"])
            lead.update({"phone": cand["phone"], "specialty": cand["specialty"], "npi": cand["npi"], "address": cand["address"],
                         "first": cand["first"], "last": cand["last"], "title": cand["title"],
                         "vertical": self.q.get("industry") or "Medical practice"})
        elif cand["kind"] == "company":
            for k in ("website", "phone", "first", "last", "title", "email", "linkedin", "address", "country"):
                lead[k] = lead[k] or cand.get(k, "")
            if cand.get("email") and lead["estatus"] == "Unverified":
                lead["estatus"] = cand.get("estatus") or "Unverified"
            lead["vertical"] = lead["vertical"] or cand.get("industry", "")
            if lead["emp"] is None and cand.get("employees"):
                lead["emp"] = _employees(cand["employees"])
            lead["priority"] = min(lead["priority"], cand.get("priority", 9))
            sig = cand.get("signal", "")
            if sig:
                hiring = "hiring" in sig.lower()
                lead["hiring" if hiring else "expand"] = "Y"
                text = re.sub(r"^\s*(we'?re\s+)?hiring\s*(for|:|-)?\s*", "", sig, flags=re.I) if hiring else sig
                lead["detail"] = "; ".join(x for x in (lead["detail"], text or sig) if x)
            if cand.get("evidence"):
                lead["urls"].append("Evidence: " + cand["evidence"])
            if cand.get("signal_date") and (not lead["sigdate"] or cand["signal_date"] > lead["sigdate"]):
                lead["sigdate"] = cand["signal_date"]
            if cand.get("source_note"):
                lead["urls"].append("Source: " + cand["source_note"])
        else:                                    # a Google Places listing: the business has a profile, and its website field is a real gap signal
            lead["website"] = lead["website"] or cand.get("website", "")
            lead["phone"] = lead["phone"] or cand.get("phone", "")
            lead["hasgbp"] = "Y"
            lead["hasweb"] = "Y" if lead["website"] else (lead["hasweb"] or "N")
            if isinstance(cand.get("reviews"), (int, float)):
                lead["reviews"] = cand["reviews"]

    def _presence(self, lead):
        if not lead["provider"] or lead["hasweb"] or lead["hasgbp"]:
            return
        row = self.presence_data.get(lead["npi"]) or self.presence_data.get(norm_name(lead["company"]))
        if not row and self.checker:
            row = self.checker.check(lead["company"], lead["city"], lead["state"], lead["phone"])
        if row:
            lead["hasweb"], lead["hasgbp"], lead["reviews"] = row["hasweb"], row["hasgbp"], row["reviews"]

    def _enrich(self, lead):
        self._presence(lead)
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
        if self.contact_finder and lead["website"] and not lead["email"] and not lead.get("_contacts_done"):
            lead["_contacts_done"] = True
            c = self.contact_finder.find(lead["website"], lead["first"], lead["last"])
            if c["email"]:
                lead["email"], lead["estatus"] = c["email"], c["estatus"]
            lead["phone"] = lead["phone"] or c["phone"]
            lead["linkedin"] = lead["linkedin"] or c["linkedin"]
            if c["page"]:
                lead["urls"].append("Contact found on: " + c["page"])
            elif c["note"]:
                lead["urls"].append(c["note"].capitalize())
        if self.do_audit and lead["website"] and not lead["outdated"]:
            r = audit.audit_site(lead["website"])
            lead["outdated"], lead["audit_note"] = r["outdated"], r["note"]
            key = os.environ.get("PAGESPEED_API_KEY")
            if key and lead["psi"] is None:
                lead["psi"] = audit.psi_score(lead["website"], key)

    # ---- scoring / selection ------------------------------------------
    def _finish(self, lead):
        lead.update(scoring.score(lead, self.cfg, [self.q["industry"]] if self.q.get("industry") else (), self.today))
        lead["strength"] = scoring.strength(lead, self.cfg, self.today)
        lead["size_class"] = scoring.size_class(lead, self.cfg)
        lead["why"] = scoring.why(lead)
        lead["signal"], lead["subject"], lead["body"] = drafts.draft(lead, self.cfg, self.templates)
        lead["notes"] = " | ".join(dict.fromkeys(lead["urls"]))
        if lead["provider"] and not (lead["hasweb"] or lead["hasgbp"]):
            lead["notes"] = (lead["notes"] + " | " if lead["notes"] else "") + "Check presence: " + presence.check_links(lead["company"], lead["city"], lead["state"])
        need = [n for n, missing in (("web-presence check", lead["provider"] and not (lead["hasweb"] or lead["hasgbp"])), ("website", not lead["website"] and lead["hasweb"] != "N"), ("decision-maker email", not lead["email"]),
                                     ("phone", not lead["phone"]), ("employee count", lead["emp"] is None and not lead["provider"])) if missing]
        lead["next_step"] = ("Find " + ", ".join(need)) if need else "Verify email, then review draft"

    def _ready(self):
        want = {"hot": {"hot"}, "warm": {"hot", "warm"}, "any": {"hot", "warm", "cold"}}[self.q.get("signal", "warm")]
        out = []
        for key, lead in self.pool.items():
            if key in self.seen:
                continue
            self._finish(lead)
            if self.cfg.get("exclude_large") and lead["size_class"] == "Large":
                continue
            if lead["strength"] in want:
                out.append((key, lead))
        out.sort(key=lambda kv: ((kv[1]["specialty"] if self.group_by_specialty else ""), (kv[1]["priority"] if self.priority_first else 0), -kv[1]["total"], kv[1]["priority"], -kv[1]["n_postings"],
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
            with open(self.seen_path, "w", encoding="utf-8") as fh:
                json.dump(sorted(self.seen), fh)
        return [lead for _, lead in ready]
