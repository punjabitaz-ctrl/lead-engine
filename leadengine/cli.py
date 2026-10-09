import argparse
import datetime as dt
import os
import sys

from . import config, export, sources
from .engine import Engine, load_enrichment

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
        elif n == "places":
            if not args.industry:
                raise SystemExit("--industry is required for the places source")
            gens.append(sources.places_businesses(cities, args.industry))
        else:
            raise SystemExit(f"Unknown source {n}")
    return (b for g in gens for b in g)


def summarize(leads):
    print(f"\n{'#':>3}  {'Score':>5} {'Gr':>2} {'Tier':<5} {'Company':<42} Signal")
    for i, ld in enumerate(leads, 1):
        print(f"{i:>3}  {ld['total']:>5} {ld['grade']:>2} {ld['tier']:<5} {ld['company'][:42]:<42} {ld['detail'][:60]}")


def run(args):
    interactive = not args.city
    if interactive:
        args.city = [c.strip() for c in ask("City, ST (separate several with ';')").split(";") if c.strip()]
        args.industry = ask("Industry (blank to skip)", args.industry or "")
        args.profession = ask("Profession / role you want to reach or that signals need", args.profession or "web developer, marketing manager")
        args.interest = ask("Interest level (hot / warm / any)", args.interest)
    cities = [parse_city(c) for c in args.city]
    professions = [p.strip() for p in (args.profession or "").split(",") if p.strip()]
    cfg = config.load(args.config)
    query = {"industry": args.industry, "professions": professions, "interest": args.interest}
    seen = None if args.fresh else os.path.join(args.state_dir, "seen.json")
    eng = Engine(query, cfg, build_sources(args, cities, professions), seen_path=seen, do_audit=args.audit,
                 enrichment=load_enrichment(args.enrich) if args.enrich else None)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_no = 0
    while True:
        batch_no += 1
        eng.fill(args.target)
        leads = eng.take(args.target)
        if not leads:
            print("No new qualifying leads. Sources are exhausted; widen the profession list, interest level, or cities.")
            break
        summarize(leads)
        st = eng.stats
        print(f"\nScanned {st['scanned']} records: dropped {st['enterprise_or_staffing']} enterprise/staffing, "
              f"{st['irrelevant_role']} irrelevant roles, {st['part_time']} part-time, {st['anonymous']} anonymous.")
        base = os.path.join(args.out, f"leads-{stamp}-b{batch_no}")
        export.write_csv(base + ".csv", leads)
        if os.path.exists(args.template):
            export.write_workbook(args.template, base + ".xlsx", leads, cfg, [c for c, _ in cities], args.industry)
        print(f"Saved {len(leads)} leads -> {base}.csv" + (f" and {base}.xlsx" if os.path.exists(args.template) else ""))
        if len(leads) < args.target:
            print(f"Only {len(leads)} of the {args.target} requested qualified: sources are exhausted. "
                  "Try --interest any, more professions, nearby cities, or add the places source.")
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
    ap.add_argument("--interest", choices=["hot", "warm", "any"], default="warm")
    ap.add_argument("--source", action="append", choices=["csv", "adzuna", "places"])
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
