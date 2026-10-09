import argparse
import datetime as dt
import json
import os
import sys

from . import config, export, sources
from .engine import Engine, load_enrichment
from .presence import PlacesChecker, load_presence

STATES = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
          "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
          "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
          "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
          "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
          "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
          "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
          "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
          "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
          "wisconsin": "WI", "wyoming": "WY"}


def parse_city(text):
    city, _, st = text.rpartition(",")
    if not city:
        raise SystemExit(f"Use 'City, ST' (got {text!r})")
    st = st.strip()
    return city.strip(), STATES.get(st.lower(), st.upper())


def ask(prompt, default=""):
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def build_sources(args, cities, professions):
    names = args.source or (["csv"] if args.postings else [])
    if not names:
        names = [n for n, ok in (("adzuna", os.environ.get("ADZUNA_APP_ID")), ("places", os.environ.get("GOOGLE_PLACES_API_KEY"))) if ok]
    if not names:
        raise SystemExit("No data source. Use --postings FILE.csv, or set ADZUNA_APP_ID/ADZUNA_APP_KEY and/or "
                         "GOOGLE_PLACES_API_KEY. See README.")
    gens = []
    for n in names:
        if n == "csv":
            gens.append(sources.csv_postings(args.postings, cities))
        elif n == "adzuna":
            gens.append(sources.adzuna_postings(cities, professions))
        elif n == "nppes":
            gens.append(sources.nppes_providers(cities, taxonomies_for(args)))
        elif n == "places":
            if not args.industry:
                raise SystemExit("--industry is required for the places source")
            gens.append(sources.places_businesses(cities, args.industry))
        else:
            raise SystemExit(f"Unknown source {n}")
    return (b for g in gens for b in g)


def taxonomies_for(args):
    """--taxonomy wins; otherwise --tier 1 (default), 2, 3 or all, from data/segments.json."""
    if args.taxonomy:
        return [t.strip() for t in args.taxonomy.split(",") if t.strip()]
    with open(os.path.join(os.path.dirname(__file__), "data", "segments.json"), encoding="utf-8") as fh:
        seg = json.load(fh)
    tiers = ["focus", "tier1", "tier2", "tier3"] if args.tier == "all" else ["focus" if args.tier == "focus" else f"tier{args.tier}"]
    return [t for k in tiers for t in seg[k]["taxonomies"]]


def summarize(leads):
    print(f"\n{'#':>3}  {'Score':>5} {'Gr':>2} {'Sig':<5} {'Company':<42} Signal")
    for i, ld in enumerate(leads, 1):
        print(f"{i:>3}  {ld['total']:>5} {ld['grade']:>2} {ld['strength']:<5} {ld['company'][:42]:<42} {ld['detail'][:60]}")


CHECKS = [
    ("npiregistry.cms.hhs.gov", "NJ provider registry (required)", "https://npiregistry.cms.hhs.gov/api/?version=2.1&state=NJ&limit=1&taxonomy_description=Ophthalmology"),
    ("places.googleapis.com", "Google Places presence checks", "https://places.googleapis.com/"),
    ("data.cms.gov", "Medicare spending by specialty", "https://data.cms.gov/"),
    ("www.cms.gov", "CMS specialty tables", "https://www.cms.gov/"),
    ("download.medicaid.gov", "NADAC drug costs", "https://download.medicaid.gov/"),
    ("rwjbh.org", "RWJ New Brunswick price file", "https://rwjbh.org/"),
    ("saintpetershcs.com", "Saint Peter's price file", "https://www.saintpetershcs.com/"),
    ("hackensackmeridianhealth.org", "Raritan Bay price file", "https://www.hackensackmeridianhealth.org/"),
    ("www1.pennmedicine.org", "Penn Princeton price file", "https://www1.pennmedicine.org/"),
    ("mzsrtwrbpdpehthwmkwt.supabase.co", "click/visit tracker", "https://mzsrtwrbpdpehthwmkwt.supabase.co/functions/v1/lead-tracker/t"),
]


def doctor():
    """Preflight: which hosts the sandbox can reach and which keys are set. Prints no secret values."""
    import urllib.error
    import urllib.request
    blocked = []
    for host, purpose, url in CHECKS:
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "LeadEngine doctor"}), timeout=10)
            status = "reachable"
        except urllib.error.HTTPError as exc:          # the site answered, even if with an error code
            status = f"reachable (HTTP {exc.code})"
        except Exception as exc:
            status = f"BLOCKED ({type(exc).__name__}: {str(exc)[:60]})"
            blocked.append(host)
        print(f"{host:<36} {purpose:<34} {status}")
    for var, purpose in (("GOOGLE_PLACES_API_KEY", "presence checks"), ("ADZUNA_APP_ID", "optional job signals")):
        print(f"{var:<36} {purpose:<34} {'set' if os.environ.get(var) else 'NOT SET'}")
    if blocked:
        print("\nAdd the BLOCKED hosts under Allowed domains (cloud environment menu > Edit > Network access), then start a new session.")
    return 1 if blocked else 0


def run(args):
    interactive = not args.city and not args.state and not args.county
    if interactive:
        args.city = [c.strip() for c in ask("City, ST (separate several with ';')").split(";") if c.strip()]
        args.industry = ask("Industry (blank to skip)", args.industry or "")
        args.profession = ask("Profession / role you want to reach or that signals need", args.profession or "web developer, marketing manager")
        args.signal = ask("Signal strength (hot / warm / any)", args.signal or "warm")
    if args.county:
        cities = sources.county_cities(args.county)
    elif args.city:
        cities = [parse_city(c) for c in args.city]
    elif (args.state or "").upper() == "NJ":
        cities = sources.nj_cities()
    else:
        raise SystemExit("Give --county Middlesex, --city 'City, ST' or --state NJ")
    professions = [p.strip() for p in (args.profession or "").split(",") if p.strip()]
    cfg = config.load(args.config)
    signal = args.signal or ("any" if "nppes" in (args.source or []) else "warm")
    query = {"industry": args.industry, "professions": professions, "signal": signal}
    seen = None if args.fresh else os.path.join(args.state_dir, "seen.json")
    checker = (PlacesChecker(args.state_dir, args.max_places_calls, args.monthly_places_cap)
               if args.presence_check == "places" else None)
    eng = Engine(query, cfg, build_sources(args, cities, professions), seen_path=seen, do_audit=args.audit,
                 enrichment=load_enrichment(args.enrich) if args.enrich else None,
                 presence_data=load_presence(args.presence) if args.presence else None,
                 checker=checker)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    stages = [args.target] if args.target else [int(x) for x in args.stages.split(",") if x.strip()]
    batch_no = 0
    while True:
        size = stages[min(batch_no, len(stages) - 1)]
        batch_no += 1
        eng.fill(size)
        leads = eng.take(size)
        if not leads:
            print("No new qualifying leads. Sources are exhausted; widen the profession list, signal strength, or cities.")
            break
        print(f"\nStage {batch_no}: target {size}")
        summarize(leads)
        st = eng.stats
        print(f"\nScanned {st['scanned']} records: dropped {st['enterprise_or_staffing']} enterprise/staffing, "
              f"{st['irrelevant_role']} irrelevant roles, {st['part_time']} part-time, {st['anonymous']} anonymous, "
              f"{st['not_private']} not privately owned.")
        if checker:
            print(checker.cost_note() + (f"\nPlaces lookups paused: {checker.stopped}. Unchecked providers stay 'cold'." if checker.stopped else ""))
        base = os.path.join(args.out, f"leads-{stamp}-b{batch_no}")
        export.write_csv(base + ".csv", leads)
        if os.path.exists(args.template):
            export.write_workbook(args.template, base + ".xlsx", leads, cfg, [c for c, _ in cities], args.industry)
        print(f"Saved {len(leads)} leads -> {base}.csv" + (f" and {base}.xlsx" if os.path.exists(args.template) else ""))
        if len(leads) < size:
            print(f"Only {len(leads)} of the {size} requested qualified: sources are exhausted. "
                  "Try --signal any, more professions, nearby cities, or add the places source.")
            break
        nxt = stages[min(batch_no, len(stages) - 1)]
        if args.all_stages:
            continue
        if args.no_prompt or not sys.stdin.isatty():
            break
        if ask(f"Next stage: {nxt} more leads? (y/n)", "n").lower() not in ("y", "yes"):
            break


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leadengine", description="Point at a city, industry and profession; get scored leads.")
    ap.add_argument("command", nargs="?", default="run", choices=["run", "doctor"])
    ap.add_argument("--city", action="append", help="'City, ST' (repeatable). Omit to be prompted.")
    ap.add_argument("--industry", default="")
    ap.add_argument("--profession", default="")
    ap.add_argument("--signal", choices=["hot", "warm", "any"], help="signal strength to keep (default warm; any for nppes)")
    ap.add_argument("--county", action="append", help="NJ county (repeatable), e.g. --county Middlesex --county Somerset")
    ap.add_argument("--state", help="two-letter state for a statewide sweep, e.g. NJ (nppes uses data/nj_cities.txt)")
    ap.add_argument("--taxonomy", help="comma list of NPPES specialties, e.g. 'Family Medicine, Pediatrics'")
    ap.add_argument("--presence", help="CSV of web-presence results (npi or company, has_website, has_gbp, reviews)")
    ap.add_argument("--presence-check", choices=["places"], help="look each provider up in Google Places (needs a key)")
    ap.add_argument("--tier", choices=["focus", "1", "2", "3", "all"], default="focus", help="NPPES specialty set from data/segments.json (default: focus = cardiology + ophthalmology)")
    ap.add_argument("--max-places-calls", type=int, default=200, help="hard cap on Places lookups per run")
    ap.add_argument("--monthly-places-cap", type=int, default=1000, help="hard cap per calendar month (default = Google's listed free allowance)")
    ap.add_argument("--source", action="append", choices=["csv", "adzuna", "places", "nppes"])
    ap.add_argument("--postings", help="CSV of job postings (metro,company,title,location,posted,job_type,comp,url)")
    ap.add_argument("--target", type=int, help="one batch of exactly this size (overrides --stages)")
    ap.add_argument("--stages", default="59,100,250", help="batch sizes in order; the last repeats (default 59,100,250)")
    ap.add_argument("--all-stages", action="store_true", help="run every stage without asking in between")
    ap.add_argument("--audit", action="store_true", help="fetch each website and flag outdated sites (needs internet)")
    ap.add_argument("--enrich", help="CSV with websites / sizes / contacts to merge (company,website,employees,phone,first,last,title,email,linkedin,estatus)")
    ap.add_argument("--template", default="lead-engine-template.xlsx")
    ap.add_argument("--out", default="output")
    ap.add_argument("--config")
    ap.add_argument("--state-dir", default=".leadengine")
    ap.add_argument("--fresh", action="store_true", help="ignore the record of leads already delivered")
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args(argv)
    if args.command == "doctor":
        raise SystemExit(doctor())
    run(args)
