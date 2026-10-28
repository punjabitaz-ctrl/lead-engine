"""Enrich and check a compiled lead list in place, then report on its quality.

  leadengine campaign enrich  <name> [--list approved|pending|rejected|review|FILE] [--steps ...] [--verifier zerobounce --max-verifications N]
  leadengine campaign quality <name> [--list ...]          read-only: the same report without changing anything or using the network

Steps (default: all the free ones):
  contacts   rows with a website and no email: read the business's own site for published emails, phone and LinkedIn (robots.txt respected)
  websites   the website answers, is not parked, does not redirect to another business
  email      the email domain receives mail (DNS); a domain with no mail servers makes the address Invalid
  npi        the NPI is active in the NPPES registry and its name matches
  verify     paid mailbox check with your own ZeroBounce or NeverBounce key; only this marks an address Valid (needs --verifier)
Offline checks (syntax, phone rules, NPI check digit, duplicates, mismatched domains) always run.

Each row gains: Phone (formatted), Email Check, Website Check, NPI Check, Issues, Confidence (0-100), Last Verified, Checked.
The list is rewritten with a .bak copy of the previous version; nothing is ever deleted. Rows are never dropped: problems are flagged for you to decide."""
import datetime as dt
import json
import os
import re
import shutil
import time

from . import campaign, verify
from .contacts import ContactFinder, domain_of

STEPS = ("contacts", "websites", "email", "npi", "verify")
FREE = ("contacts", "websites", "email", "npi")
ADDED = ["Phone (formatted)", "Email Check", "Website Check", "NPI Check", "Issues", "Confidence", "Last Verified", "Checked"]
LISTS = {"approved": "approved.csv", "pending": "pending.csv", "rejected": "rejected.csv"}
STALE_DAYS = 90


def list_paths(name, root, which):
    """-> paths of the CSVs a --list value names: approved, pending, rejected, review (every pack), all, or a file path."""
    d = campaign.folder(name, root)
    if which in LISTS:
        return [os.path.join(d, LISTS[which])]
    if which == "review":
        return campaign._review_packs(name, root)
    if which == "all":
        return [os.path.join(d, f) for f in LISTS.values()]
    return [which]


def _row_check(row, today, checker=None, steps=(), finder=None, paid=None):
    """Runs the checks on one row and writes the results into it. A check that does not run this time keeps its last result.
    -> list of steps that ran."""
    ran = []
    if finder and "contacts" in steps and (row.get("Website") or "").strip() and not (row.get("Email") or "").strip():
        got = finder.find(row["Website"], row.get("First Name", ""), row.get("Last Name", ""))
        if got.get("email"):
            row["Email"], row["Email Status"] = got["email"], got["estatus"]
            row["Email Check"] = ""
        if got.get("phone") and not (row.get("Phone") or "").strip():
            row["Phone"] = got["phone"]
        if got.get("linkedin") and not (row.get("LinkedIn URL") or "").strip():
            row["LinkedIn URL"] = got["linkedin"]
        if got.get("page") or got.get("note"):
            note = f"Contact found on: {got['page']}" if got.get("page") else got["note"]
            if note not in (row.get("Notes") or ""):
                row["Notes"] = f"{row['Notes']} | {note}" if row.get("Notes") else note
        ran.append("contacts")
    off = verify.offline(row)
    issues = list(off["issues"])
    row["Phone (formatted)"] = off["phone"]
    email = (row.get("Email") or "").strip()
    status = (row.get("Email Status") or "").strip()
    # email: offline syntax first, then the domain's mail servers, then a paid mailbox check
    if off["checks"]["email"] != "syntax ok":
        echeck = off["checks"]["email"]
        if off["email_status"] == "Invalid":
            status = "Invalid"
    else:
        echeck = row.get("Email Check") or verify.NOT_CHECKED
        if echeck in ("invalid", "none"):
            echeck = verify.NOT_CHECKED
        if checker and "email" in steps:
            v = checker.mail_domain(email.split("@", 1)[1].lower())
            echeck = "domain receives mail" if v == "ok" else v
            if v != verify.NOT_CHECKED:
                ran.append("email")
        if paid and "verify" in steps and echeck not in ("no mail servers", "domain does not exist"):
            got = paid.check(email)
            if got:
                status, echeck = got, f"{paid.name}: {got.lower()}"
                ran.append("verify")
        if echeck in ("no mail servers", "domain does not exist"):
            status = "Invalid"
            issues.append(f"email domain: {echeck}")
    row["Email Status"] = status or ("Unverified" if email else "")
    row["Email Check"] = echeck
    # website: answers, not parked, not redirected to someone else
    if not (row.get("Website") or "").strip():
        wcheck = "none"
    elif verify.url_check(row["Website"]):
        wcheck = "not a business website"
    else:
        wcheck = row.get("Website Check") or verify.NOT_CHECKED
        if wcheck in ("none", "not a business website"):
            wcheck = verify.NOT_CHECKED
        if checker and "websites" in steps:
            wcheck, _ = checker.website(row["Website"])
            if wcheck != verify.NOT_CHECKED:
                ran.append("websites")
        if wcheck in ("down", "parked"):
            issues.append(f"website is {wcheck}")
        elif wcheck.startswith("redirects to"):
            issues.append(f"website {wcheck}")
    row["Website Check"] = wcheck
    # NPI: check digit offline, then the NPPES registry
    ncheck = off["checks"].get("npi", "")
    if ncheck == "check digit ok":
        prev = row.get("NPI Check") or ""
        ncheck = prev if prev and prev not in ("invalid", "check digit ok") else ncheck
        if checker and "npi" in steps:
            ncheck = checker.npi(row["NPI"], row.get("Company", ""), row.get("Last Name", ""))
            if ncheck != verify.NOT_CHECKED:
                ran.append("npi")
        if ncheck == "deactivated":
            issues.append("NPI is not active in the registry")
        elif ncheck == "not found":
            issues.append("NPI not found in the registry")
        elif ncheck.startswith("name differs"):
            issues.append("registry " + ncheck)
    row["NPI Check"] = ncheck
    if [s for s in ran if s != "contacts"]:
        row["Last Verified"] = today.isoformat()
    last = row.get("Last Verified") or ""
    if not last:
        issues.append("never verified")
    else:
        try:
            age = (today - dt.date.fromisoformat(last)).days
        except ValueError:
            age = STALE_DAYS + 1
        if age > STALE_DAYS:
            issues.append(f"not verified for {age} days")
    row["_issues"] = issues
    return ran


def _finish(rows, today, ran_by_row):
    dups = verify.duplicates(rows)
    for i, r in enumerate(rows):
        issues = r.pop("_issues", [])
        if i in dups:
            issues.append(dups[i])
        r["Issues"] = "; ".join(issues)
        r["Confidence"] = verify.confidence(issues, r.get("Email Status", ""))
        if ran_by_row.get(i):
            prev = [x for x in (r.get("Checked") or "").split(", ") if x and not x.startswith(today.isoformat())]
            r["Checked"] = ", ".join([f"{today.isoformat()}: {'+'.join(ran_by_row[i])}"] + prev)[:200]


def _kind(issue):
    """Groups issues that differ only by the value in them: 'NPI 123 fails...' and 'NPI 456 fails...' count together."""
    if issue.startswith("duplicate of row"):
        return "duplicate"
    if issue.startswith("not verified for"):
        return f"not verified in the last {STALE_DAYS} days"
    return re.sub(r"'[^']*'|(?<![\w-])\d+(?![\w-])|[\w-]+(\.[\w-]+)+,?", "...", issue)


def summarize(rows):
    """Coverage and validity per field, issue counts, and the rows most worth a look."""
    n = len(rows)
    pct = lambda k: round(100 * k / n) if n else 0
    has = lambda col: sum(1 for r in rows if (r.get(col) or "").strip())
    status = {}
    for r in rows:
        s = (r.get("Email Status") or "").strip() or ("none" if not (r.get("Email") or "").strip() else "blank")
        status[s] = status.get(s, 0) + 1
    counts = {}
    for r in rows:
        for i in filter(None, (r.get("Issues") or "").split("; ")):
            k = _kind(i)
            counts[k] = counts.get(k, 0) + 1
    conf = [int(r["Confidence"]) for r in rows if str(r.get("Confidence", "")).isdigit()]
    return {"rows": n, "with_email": pct(has("Email")), "with_phone": pct(has("Phone")), "with_website": pct(has("Website")),
            "with_contact_name": pct(has("First Name")), "email_status": status,
            "valid_phone": pct(sum(1 for r in rows if r.get("Phone (formatted)"))),
            "website_live": pct(sum(1 for r in rows if r.get("Website Check") == "live")),
            "checked": pct(sum(1 for r in rows if r.get("Last Verified"))),
            "confidence_avg": round(sum(conf) / len(conf)) if conf else None,
            "confidence_bands": {"80-100": sum(1 for c in conf if c >= 80), "50-79": sum(1 for c in conf if 50 <= c < 80), "0-49": sum(1 for c in conf if c < 50)},
            "issues": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
            "worst": [(r.get("Company", ""), r.get("Confidence", ""), r.get("Issues", "")) for r in
                      sorted(rows, key=lambda r: int(r["Confidence"]) if str(r.get("Confidence", "")).isdigit() else 101)[:10]]}


def report_md(name, label, s, today, network_failures=0):
    lines = [f"# Data quality: {name} / {label}  ({today.isoformat()})", "",
             f"{s['rows']} rows. Email on {s['with_email']}%, phone on {s['with_phone']}% ({s['valid_phone']}% valid), website on {s['with_website']}% "
             f"({s['website_live']}% checked live), a contact name on {s['with_contact_name']}%. {s['checked']}% of rows have been checked.", "",
             "Email status: " + ", ".join(f"{k} {v}" for k, v in sorted(s["email_status"].items())) +
             ". Only a paid mailbox check marks an address Valid; addresses read off a website are Risky.", ""]
    if s["confidence_avg"] is not None:
        b = s["confidence_bands"]
        lines += [f"Confidence (a ranking heuristic, not a probability): average {s['confidence_avg']}; {b['80-100']} rows at 80-100, "
                  f"{b['50-79']} at 50-79, {b['0-49']} below 50.", ""]
    if network_failures:
        lines += [f"{network_failures} network checks could not run; those fields say 'not checked'. Run again where the network is open.", ""]
    if s["issues"]:
        lines += ["## Issues", ""] + [f"* {k}: {v}" for k, v in s["issues"].items()] + [""]
    if s["worst"]:
        lines += ["## Lowest confidence (check these first)", ""] + [f"* {c} ({conf}): {i}" for c, conf, i in s["worst"] if i] + [""]
    return "\n".join(lines) + "\n"


def run(name, root=campaign.ROOT, which="approved", steps=FREE, checker=None, finder=None, paid=None, today=None, max_sites=100,
        delay=1.0, sleep=time.sleep, write=True, state_dir=".leadengine"):
    """Enrich and check one or more lists. -> {"lists": {path: summary}, "report": path, "network_failures": n}"""
    campaign.load(name, root)
    today = today or dt.date.today()
    bad = [s for s in steps if s not in STEPS]
    if bad:
        raise SystemExit(f"Unknown step(s) {', '.join(bad)}; choose from {', '.join(STEPS)}")
    if "verify" in steps and paid is None:
        raise SystemExit("The verify step is a paid check: add --verifier zerobounce|neverbounce and --max-verifications N")
    if steps and checker is None and any(s in steps for s in ("websites", "email", "npi")):
        checker = verify.Checker(today=today)
    if "contacts" in steps and finder is None:
        finder = ContactFinder(state_dir, max_sites=max_sites, delay=delay, sleep=sleep)
    out, all_rows = {}, []
    for path in list_paths(name, root, which):
        rows, fields = campaign._read_csv(path)
        if not rows:
            continue
        ran = {}
        for i, r in enumerate(rows):
            ran[i] = _row_check(r, today, checker, steps, finder, paid)
        _finish(rows, today, ran)
        if write and steps:
            shutil.copyfile(path, path + ".bak")
            campaign._write_csv(path, rows, fields + [c for c in ADDED + ["Email", "Email Status", "Phone", "LinkedIn URL", "Notes"] if c not in fields])
        out[path] = summarize(rows)
        all_rows += rows
    if not out:
        raise SystemExit(f"No rows in the {which} list(s) of {name}")
    s = summarize(all_rows)
    fails = checker.failures if checker else 0
    path = os.path.join(campaign.folder(name, root), f"quality-{which if which in LISTS or which in ('review', 'all') else 'file'}-{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report_md(name, which, s, today, fails))
    campaign.log(name, "enrich" if steps else "quality", root, list=which, steps=list(steps), rows=s["rows"], network_failures=fails,
                 paid_checks=paid.used if paid else 0)
    return {"lists": out, "summary": s, "report": path, "network_failures": fails, "paid_checks": paid.used if paid else 0}


def main(argv, root, quality_only=False):
    import argparse
    ap = argparse.ArgumentParser(prog="leadengine campaign " + ("quality" if quality_only else "enrich"), description=__doc__.split("\n")[0])
    ap.add_argument("name")
    ap.add_argument("--list", default="approved", help="approved, pending, rejected, review (every pack), all, or a CSV path")
    if not quality_only:
        ap.add_argument("--steps", default=",".join(FREE), help=f"comma list from {', '.join(STEPS)} (default: the free ones)")
        ap.add_argument("--max-sites", type=int, default=100, help="most websites read for contacts this run")
        ap.add_argument("--verifier", choices=sorted(verify.VERIFIERS), help="paid mailbox check with your own key (billed by the provider)")
        ap.add_argument("--max-verifications", type=int, default=0, help="most paid checks this run (required with --verifier)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    steps = () if quality_only else tuple(s.strip() for s in a.steps.split(",") if s.strip())
    paid = None
    if not quality_only and a.verifier:
        if a.max_verifications <= 0:
            raise SystemExit("Set --max-verifications N: each check is billed by the provider")
        paid = verify.PaidVerifier(a.verifier, a.max_verifications, ".leadengine")
        steps = tuple(dict.fromkeys(steps + ("verify",)))
    res = run(a.name, root, a.list, steps, paid=paid, max_sites=getattr(a, "max_sites", 100), write=not quality_only)
    if a.json:
        print(json.dumps({k: v for k, v in res.items() if k != "lists"}, indent=2))
    else:
        s = res["summary"]
        print(f"{s['rows']} rows: email {s['with_email']}%, phone {s['with_phone']}%, website {s['website_live']}% live; "
              f"average confidence {s['confidence_avg']}. Report: {res['report']}")
        if res["network_failures"]:
            print(f"  note: {res['network_failures']} network checks could not run (they say 'not checked')")
        if res["paid_checks"]:
            print(f"  paid checks used: {res['paid_checks']}")
    return 0
