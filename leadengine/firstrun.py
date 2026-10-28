"""First run on your own computer, in one command: check the network, create the campaign, find leads, check them, report, export.

  python3 -m leadengine first-run                         NJ cardiology and ophthalmology practices in Middlesex County, 25 leads
  python3 -m leadengine first-run --county Somerset --target 50
  python3 -m leadengine first-run --demo                  the same steps on built-in sample data, with no network (nothing is real)
  python3 -m leadengine first-run --sender my-sender.json  copy your sender details into the campaign and check them (finds no leads)

It never contacts anyone and uses no paid service. Run it from the repo folder (it uses lead-engine-template.xlsx there).
At the end it says whether your sender details are ready for email, and what to do next."""
import argparse
import contextlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from . import campaign, enrich, listexport, mailer, mailing, sources, verify

NEED = [("npiregistry.cms.hhs.gov", "https://npiregistry.cms.hhs.gov/api/?version=2.1&state=NJ&limit=1&taxonomy_description=Ophthalmology",
         "finding practices (required)"),
        ("dns.google", "https://dns.google/resolve?name=example.com&type=MX", "checking email domains (enrich)")]


def reachable(url):
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "LeadEngine first-run"}), timeout=10).close()
        return True
    except urllib.error.HTTPError:
        return True                                   # the host answered
    except Exception:
        return False


# ---- demo data: made-up practices, fictional 555-01xx numbers, so the whole flow can be seen offline ----------------------
def _demo_page(url):
    if "enumeration_type=NPI-2" not in url or "skip=0" not in url:
        return {"results": []}
    spec = "Ophthalmology" if "Ophthalmology" in url else "Cardiovascular Disease"
    city = urllib.parse.unquote_plus(url.split("city=")[1].split("&")[0]).title() if "city=" in url else "Edison"
    if city not in ("Edison", "New Brunswick", "Woodbridge"):
        return {"results": []}
    n = {"Edison": 1, "New Brunswick": 2, "Woodbridge": 3}[city] + (10 if spec == "Ophthalmology" else 0)
    word = "Eye" if spec == "Ophthalmology" else "Heart"
    res = []
    for k in range(2):
        res.append({"number": "", "enumeration_type": "NPI-2",
                    "basic": {"organization_name": f"DEMO {city.upper()} {word.upper()} ASSOCIATES {k + 1}", "status": "A",
                              "authorized_official_first_name": "ALEX", "authorized_official_last_name": "SAMPLE",
                              "authorized_official_title_or_position": "PRACTICE OWNER"},
                    "addresses": [{"address_purpose": "LOCATION", "address_1": f"{100 + n} DEMO ST", "city": city.upper(), "state": "NJ",
                                   "telephone_number": f"732-555-01{n * 2 + k:02d}"}],
                    "taxonomies": [{"desc": spec, "primary": True}]})
    return {"results": res}


class _DemoChecker(verify.Checker):
    def __init__(self):
        super().__init__(opener=self._open, fetch=lambda url, timeout=15: (url, "<html>Demo practice</html>"))

    @staticmethod
    def _open(req, timeout=15):
        import io
        body = {"Status": 0, "Answer": [{"type": 15, "data": "10 mx.example"}]} if "dns.google" in req.full_url else {"results": []}
        return contextlib.closing(io.BytesIO(json.dumps(body).encode()))


@contextlib.contextmanager
def _demo_network():
    real = sources._http_json
    sources._http_json = lambda url, data=None, headers=None, timeout=20: _demo_page(url)
    try:
        yield
    finally:
        sources._http_json = real


# ---- the run ---------------------------------------------------------------------------
def first_run(name, state="NJ", counties=("Middlesex",), target=25, root=campaign.ROOT, demo=False, out=print):
    out(("DEMO: made-up data, no network. " if demo else "") + f"First run for {name}: {state}, {', '.join(counties)}, up to {target} leads.\n")
    # 1. network
    if not demo:
        ok = {h: reachable(u) for h, u, _ in NEED}
        for h, _, why in NEED:
            out(f"  {h:<26} {'reachable' if ok[h] else 'NOT reachable'}   {why}")
        if not ok["npiregistry.cms.hhs.gov"]:
            raise SystemExit("\nThe NPI Registry is not reachable from this computer, so no practices can be found. Check the internet connection "
                             "(a work VPN or firewall can block it) and run this again.")
        out("")
    # 2. campaign
    d = campaign.folder(name, root)
    if os.path.exists(os.path.join(d, "spec.json")):
        out(f"Using the existing campaign in {d}/")
    else:
        _, problems = campaign.init(name, state, counties=list(counties), root=root)
        out(f"Created {d}/ (spec.json, config.json)")
        if problems:
            raise SystemExit("The campaign has problems:\n  - " + "\n  - ".join(problems))
    # 3. find
    before = set(campaign._review_packs(name, root))
    with (_demo_network() if demo else contextlib.nullcontext()):
        made = campaign.run_discover(name, root, target=target)
    new = [p for p in made if p not in before]
    if not new and before:
        raise SystemExit("No new leads: what these searches return is already in your review packs. Try another county (--county Somerset) "
                         "or a larger --target.")
    if not new:
        raise SystemExit("No leads were found. Try another county (--county Somerset) or a larger --target; the lines above say which searches came back empty.")
    rows = sum(len(campaign._read_csv(p)[0]) for p in new)
    out(f"\nFound {rows} leads: {', '.join(os.path.relpath(p) for p in new)}")
    # 4. check (free steps only; the contacts step needs websites, which registry leads do not have)
    res = enrich.run(name, root, "review", ("websites", "email", "npi"), checker=_DemoChecker() if demo else None, finder=None)
    s = res["summary"]
    out(f"Checked them: phone on {s['with_phone']}% ({s['valid_phone']}% valid), email on {s['with_email']}%, average confidence {s['confidence_avg']}.")
    if res["network_failures"]:
        out(f"  {res['network_failures']} checks could not run and say 'not checked'.")
    out(f"Quality report: {os.path.relpath(res['report'])}")
    # 5. export
    xlsx = os.path.join(d, "exports", f"{name}-first-run.xlsx")
    os.makedirs(os.path.dirname(xlsx), exist_ok=True)
    rows_all, _ = listexport.load(name, root, "review")
    cols = listexport.columns("contact", rows_all, "xlsx")
    listexport.write_xlsx(xlsx, rows_all, cols, [("Campaign", name), ("List", "review packs from the first run"), ("Rows", len(rows_all)),
                                                  ("Data note", listexport.NOTE)])
    out(f"Spreadsheet: {os.path.relpath(xlsx)}")
    # 6. sender readiness (read-only)
    out("")
    problems = check_sender(name, root, out)
    out("\nNext:")
    out(f"  1. Open {os.path.relpath(new[0])}, put Keep, Drop or Unsure in the Decision column, save it.")
    out(f"  2. python3 -m leadengine campaign approve {name} {os.path.relpath(new[0])}")
    if s["with_email"] == 0:
        out("  3. Registry leads come with phone numbers and addresses, not websites or emails. Call or mail them, or add websites "
            "(a Google Places key, or your own list) before planning email. See docs/FIRST_RUN.md.")
    else:
        out("  3. Email: fill in the sender block (docs/FIRST_RUN.md), then campaign mail plan / preview / send --dry-run.")
    if demo:
        out(f"\nThis was a demo. Delete {d}/ when you are done looking.")
    return {"packs": new, "summary": s, "report": res["report"], "xlsx": xlsx, "sender_problems": problems}


def apply_sender(name, path, root=campaign.ROOT):
    """Copies the sender and mail blocks of a filled-in sender file (examples/sender_config_example.json) into the campaign's config.json."""
    with open(path, encoding="utf-8") as fh:
        src = json.load(fh)
    unknown = set(src) - {"sender", "mail", "_note"}
    if unknown:
        raise SystemExit(f"{path}: only 'sender' and 'mail' blocks are read (found {', '.join(sorted(unknown))})")
    cpath = os.path.join(campaign.folder(name, root), "config.json")
    cfg = campaign._read_json(cpath)
    skipped = []
    for block in ("sender", "mail"):
        for k, v in src.get(block, {}).items():
            if k.startswith("_"):
                continue
            if isinstance(v, str) and campaign.PLACEHOLDER.search(v):
                skipped.append(f"{block}.{k}")          # still a [placeholder]: never copied, so it cannot end up in an email
                continue
            cfg.setdefault(block, {})[k] = v
    campaign._write_json(cpath, cfg)
    campaign.log(name, "sender", root, source=os.path.basename(path), skipped=skipped)
    return cpath, skipped


def check_sender(name, root=campaign.ROOT, out=print):
    problems = mailer.sender_problems(mailing.load_cfg(name, root))
    out("Sender details for email: " + ("ready." if not problems else "not ready yet:"))
    for p in problems:
        out(f"  - {p}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leadengine first-run", description=__doc__.split("\n")[0])
    ap.add_argument("--name", help="campaign name (default nj-medical, or demo-nj-medical with --demo)")
    ap.add_argument("--state", default="NJ")
    ap.add_argument("--county", action="append", help="repeatable; default Middlesex")
    ap.add_argument("--target", type=int, default=25, help="how many leads to find (default 25)")
    ap.add_argument("--root", default=campaign.ROOT)
    ap.add_argument("--demo", action="store_true", help="built-in sample data, no network, nothing real")
    ap.add_argument("--sender", metavar="FILE", help="copy your filled-in sender file (examples/sender_config_example.json) into the campaign")
    ap.add_argument("--check-sender", action="store_true", help="only say whether the sender details are ready (finds no leads)")
    a = ap.parse_args(argv)
    name = a.name or ("demo-nj-medical" if a.demo else "nj-medical")
    if a.demo and not name.startswith("demo-"):
        raise SystemExit("A demo campaign's name must start with demo- so it is never mixed up with real leads")
    if a.sender or a.check_sender:
        campaign.load(name, a.root)
        if a.sender:
            cpath, skipped = apply_sender(name, a.sender, a.root)
            print(f"Copied the sender details into {cpath}")
            if skipped:
                print("  not copied, still a [placeholder]: " + ", ".join(skipped))
        return 1 if check_sender(name, a.root) else 0
    first_run(name, a.state, a.county or ["Middlesex"], a.target, a.root, a.demo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
