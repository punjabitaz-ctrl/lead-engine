"""Geography registry. One file per state in data/geo/<ST>.json:

  {"state": "NJ", "counties": {"Middlesex": ["Edison", ...]}, "cities": ["Newark", ...]}

`counties` maps a county to its place names (used as NPPES / Places city filters); `cities` is the statewide sweep list.
Every state and county comes from the US Census Bureau's public code lists (public domain), built with

  leadengine geo build                 downloads them from census.gov (or: --file national_place_by_county2020.txt --file national_cousub2020.txt)
  leadengine geo show NJ [--county Bergen]

Single cities work without any file (--city 'City, ST'), and so do ZIP codes (--zip 07960)."""
import json
import os
import re
import sys
import urllib.request

GEO_DIR = os.path.join(os.path.dirname(__file__), "data", "geo")


def available_states():
    return sorted(f[:-5] for f in os.listdir(GEO_DIR) if f.endswith(".json"))


def load_state(state):
    path = os.path.join(GEO_DIR, f"{state.upper()}.json")
    if not os.path.exists(path):
        raise SystemExit(f"No geography file for {state.upper()!r}. Loaded: {', '.join(available_states())}. "
                         "Run `leadengine geo build` to load every state from the Census lists; single cities (--city 'City, ST') and ZIP codes work without it.")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def county_key(name):
    """'Bergen County' / 'bergen' / 'Orleans Parish' -> 'bergen' / 'orleans' (independent cities keep 'city')."""
    return re.sub(r"\s+(county|parish|borough|census area|municipality|city and borough)$", "", name.strip(), flags=re.I).lower()


def county_cities(counties, state="NJ"):
    data = load_state(state)
    table = {county_key(k): v for k, v in data.get("counties", {}).items()}
    out, seen = [], set()
    for raw in counties:
        c = county_key(raw)
        if c not in table:
            raise SystemExit(f"County {raw!r} is not loaded for {state.upper()}. Loaded: {', '.join(k.title() for k in table) or 'none'}. "
                             "Run `leadengine geo build` to load every county, or use --city 'City, ST' / --zip.")
        for city in table[c.lower()]:
            if city not in seen:
                seen.add(city)
                out.append((city, state.upper()))
    return out


def statewide(state):
    data = load_state(state)
    cities = data.get("cities") or []
    if not cities:
        raise SystemExit(f"data/geo/{state.upper()}.json has no 'cities' list for a statewide sweep.")
    return [(c, state.upper()) for c in cities]


def is_zip(place):
    return bool(re.fullmatch(r"\d{5}", (place or "").strip()))


def resolve(geography):
    """geography: {"state": "NJ", "counties": [...], "cities": [...], "zips": [...]} -> [(place, ST)].
    ZIP codes and cities are used as given (both may be set); otherwise counties, otherwise the whole state."""
    state = (geography.get("state") or "").upper()
    zips = [(z.strip(), state) for z in geography.get("zips", []) if z.strip()]
    for z, _ in zips:
        if not is_zip(z):
            raise SystemExit(f"ZIP code {z!r} must be 5 digits")
    if zips and not state:
        raise SystemExit("ZIP codes need the geography's state (two letters)")
    out = []
    for c in geography.get("cities", []):
        city, _, st = c.rpartition(",")
        out.append((city.strip(), st.strip().upper()) if city else (c.strip(), state))
    if geography.get("counties"):
        if not state:
            raise SystemExit("counties need the geography's state (two letters)")
        out = county_cities(geography["counties"], state) + [p for p in out if p not in county_cities(geography["counties"], state)]
    out += zips
    if out:
        return out
    if not state:
        raise SystemExit("geography needs a state, or a list of 'City, ST' entries")
    return statewide(state)


# ---- building the files from the Census Bureau's code lists ------------------------------------------------
CENSUS = {
    "places": "https://www2.census.gov/geo/docs/reference/codes2020/national_place_by_county2020.txt",
    "county subdivisions": "https://www2.census.gov/geo/docs/reference/codes2020/national_cousub2020.txt",
}
SUFFIX = re.compile(r"\s+(city and borough|charter township|consolidated government( \(balance\))?|unified government( \(balance\))?|"
                    r"metro government( \(balance\))?|urban county|municipality|township|borough|village|town|city|cdp|plantation|"
                    r"gore|grant|location|purchase|reservation|unorganized territory)(\s+\(balance\))?$", re.I)
SKIP = re.compile(r"not defined|^\s*$", re.I)


def place_name(raw):
    """'Edison township' -> 'Edison'; 'Boise City city' -> 'Boise City'; 'Nashville-Davidson metropolitan government (balance)' -> as is."""
    name = re.sub(r"\s+\(balance\)$", "", raw.strip(), flags=re.I)
    stripped = SUFFIX.sub("", name)
    return stripped if stripped else name


def parse_census(text):
    """A Census pipe-delimited code list (places by county, or county subdivisions) -> {ST: {County: [place, ...]}}."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}
    head = [h.strip().upper() for h in lines[0].split("|")]
    name_col = next((i for i, h in enumerate(head) if h in ("PLACENAME", "COUSUBNAME", "NAMELSAD", "NAME")), None)
    if name_col is None or "STATE" not in head or "COUNTYNAME" not in head:
        raise SystemExit("Not a Census code list: expected STATE, COUNTYNAME and PLACENAME or COUSUBNAME columns separated by |")
    st_col, co_col = head.index("STATE"), head.index("COUNTYNAME")
    fs_col = head.index("FUNCSTAT") if "FUNCSTAT" in head else None
    out = {}
    for ln in lines[1:]:
        cells = ln.split("|")
        if len(cells) <= max(name_col, co_col, st_col):
            continue
        if fs_col is not None and len(cells) > fs_col and cells[fs_col].strip().upper() in ("F", "I"):     # fictitious or inactive
            continue
        raw = cells[name_col]
        if SKIP.search(raw):
            continue
        county = re.sub(r"\s+(county|parish)$", "", cells[co_col].strip(), flags=re.I)
        names = out.setdefault(cells[st_col].strip().upper(), {}).setdefault(county, [])
        name = place_name(raw)
        if name not in names:
            names.append(name)
    return out


def _read_source(src):
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "LeadEngine geo build"})
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
    else:
        with open(src, "rb") as fh:
            raw = fh.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def build(sources=None, states=None, out_dir=GEO_DIR):
    """Merge Census code lists into data/geo/<ST>.json. Existing hand-entered names and a curated 'cities' sweep list are kept;
    a state with no 'cities' list gets every place, so a statewide sweep covers the whole state. Returns {ST: (counties, places)}."""
    merged = {}
    for src in sources or CENSUS.values():
        for st, counties in parse_census(_read_source(src)).items():
            for county, names in counties.items():
                have = merged.setdefault(st, {}).setdefault(county, [])
                have += [n for n in names if n not in have]
    want = {s.upper() for s in states} if states else None
    done = {}
    for st, counties in sorted(merged.items()):
        if want and st not in want:
            continue
        path = os.path.join(out_dir, f"{st}.json")
        old = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                old = json.load(fh)
        table = {}
        old_counties = {county_key(k): (k, v) for k, v in old.get("counties", {}).items()}
        for county in sorted(counties):
            names = sorted(counties[county])
            prev = old_counties.pop(county_key(county), (county, []))[1]
            table[county] = names + sorted(n for n in prev if n not in names)
        for k, v in old_counties.values():                 # hand-entered counties the Census file did not name
            table[k] = v
        everything = sorted({n for v in table.values() for n in v})
        data = {"_note": "Counties and places from the US Census Bureau 2020 code lists (places by county and county subdivisions; public domain), "
                         "merged with any names entered by hand. Names are municipal names with the legal suffix removed; a few USPS mailing "
                         "names can differ.",
                "state": st, "counties": table, "cities": old.get("cities") or everything}
        os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
            fh.write("\n")
        done[st] = (len(table), len(everything))
    return done


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="leadengine geo", description="Counties and places for any US state, from the Census Bureau's code lists")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="download (or read) the Census code lists and write data/geo/<ST>.json")
    b.add_argument("--file", action="append", help="a downloaded Census code list (repeatable); default: download both from census.gov")
    b.add_argument("--state", action="append", help="only these states (repeatable)")
    b.add_argument("--out", default=GEO_DIR)
    s = sub.add_parser("show", help="list a state's counties, or one county's places")
    s.add_argument("state")
    s.add_argument("--county")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        try:
            done = build(a.file, a.state, a.out)
        except OSError as exc:
            print(f"Could not read the Census lists ({type(exc).__name__}). Download these two files on a machine with internet access, then run "
                  "`leadengine geo build --file <each file>`:\n  " + "\n  ".join(CENSUS.values()), file=sys.stderr)
            return 1
        for st, (nc, npl) in done.items():
            print(f"{st}: {nc} counties, {npl} places")
        return 0
    data = load_state(a.state)
    if a.county:
        for c, st in county_cities([a.county], a.state):
            print(c)
    else:
        for c, names in sorted(data.get("counties", {}).items()):
            print(f"{c}: {len(names)} places")
    return 0
