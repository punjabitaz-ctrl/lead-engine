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
    tiers = ["tier1", "tier2", "tier3"] if args.tier == "all" else [f"tier{args.tier}"]
    return [t for k in tiers for t in seg[k]["taxonomies"]]


def summarize(leads):
    print(f"\n{'#':>3}  {'Score':>5} {'Gr':>2} {'Sig':<5} {'Company':<42} Signal")
    for i, ld in enumerate(leads, 1):
        print(f"{i:>3}  {ld['total']:>5} {ld['grade']:>2} {ld['strength']:<5} {ld['company'][:42]:<42} {ld['detail'][:60]}")


def run(args):
    interactive = not args.city and not args.state
    if interactive:
        args.city = [c.strip() for c in ask("City, ST (separate several with ';')").split(";") if c.strip()]
        args.industry = ask("Industry (blank to skip)", args.industry or "")
        args.profession = ask("Profession / role you want to reach or that signals need", args.profession or "web developer, marketing manager")
        args.signal = ask("Signal strength (hot / warm / any)", args.signal or "warm")
    cities = [parse_city(c) for c in args.city] if args.city else (sources.nj_cities() if (args.state or "").upper() == "NJ" else [])
    if not cities:
        raise SystemExit("Give --city 'City, ST' or --state NJ")
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
    batch_no = 0
    while True:
        batch_no += 1
        eng.fill(args.target)
        leads = eng.take(args.target)
        if not leads:
            print("No new qualifying leads. Sources are exhausted; widen the profession list, signal strength, or cities.")
            break
        summarize(leads)
        st = eng.stats
        print(f"\nScanned {st['scanned']} records: dropped {st['enterprise_or_staffing']} enterprise/staffing, "
              f"{st['irrelevant_role']} irrelevant roles, {st['part_time']} part-time, {st['anonymous']} anonymous.")
        if checker:
            print(checker.cost_note() + (f"\nPlaces lookups paused: {checker.stopped}. Unchecked providers stay 'cold'." if checker.stopped else ""))
        base = os.path.join(args.out, f"leads-{stamp}-b{batch_no}")
        export.write_csv(base + ".csv", leads)
        if os.path.exists(args.template):
            export.write_workbook(args.template, base + ".xlsx", leads, cfg, [c for c, _ in cities], args.industry)
        print(f"Saved {len(leads)} leads -> {base}.csv" + (f" and {base}.xlsx" if os.path.exists(args.template) else ""))
        if len(leads) < args.target:
            print(f"Only {len(leads)} of the {args.target} requested qualified: sources are exhausted. "
                  "Try --signal any, more professions, nearby cities, or add the places source.")
        if args.no_prompt or not sys.stdin.isatty() or eng.exhausted and len(eng._ready()) == 0:
            break
        if ask(f"Want {args.target} more? (y/n)", "n").lower() not in ("y", "yes"):
            break


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leadengine", description="Point at a city, industry and profession; get scored leads.")
    ap.add_argument("command", nargs="?", default="run", choices=["run"])
    ap.add_argument("--city", action="append", help="'City, ST' (repeatable). Omit to be prompted.")
    ap.add_argument("--industry", default="")
    ap.add_argument("--profession", default="")
    ap.add_argument("--signal", choices=["hot", "warm", "any"], help="signal strength to keep (default warm; any for nppes)")
    ap.add_argument("--state", help="two-letter state for a statewide sweep, e.g. NJ (nppes uses data/nj_cities.txt)")
    ap.add_argument("--taxonomy", help="comma list of NPPES specialties, e.g. 'Family Medicine, Pediatrics'")
    ap.add_argument("--presence", help="CSV of web-presence results (npi or company, has_website, has_gbp, reviews)")
    ap.add_argument("--presence-check", choices=["places"], help="look each provider up in Google Places (needs a key)")
    ap.add_argument("--tier", choices=["1", "2", "3", "all"], default="1", help="NPPES specialty tier from data/segments.json")
    ap.add_argument("--max-places-calls", type=int, default=200, help="hard cap on Places lookups per run")
    ap.add_argument("--monthly-places-cap", type=int, default=1000, help="hard cap per calendar month (default = Google's listed free allowance)")
    ap.add_argument("--source", action="append", choices=["csv", "adzuna", "places", "nppes"])
    ap.add_argument("--postings", help="CSV of job postings (metro,company,title,location,posted,job_type,comp,url)")
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--audit", action="store_true", help="fetch each website and flag outdated sites (needs internet)")
    ap.add_argument("--enrich", help="CSV with websites / sizes / contacts to merge (company,website,employees,phone,first,last,title,email,linkedin,estatus)")
    ap.add_argument("--template", default="lead-engine-template.xlsx")
    ap.add_argument("--out", default="output")
    ap.add_argument("--config")
    ap.add_argument("--state-dir", default=".leadengine")
    ap.add_argument("--fresh", action="store_true", help="ignore the record of leads already delivered")
    ap.add_argument("--no-prompt", action="store_true")
    run(ap.parse_args(argv))
