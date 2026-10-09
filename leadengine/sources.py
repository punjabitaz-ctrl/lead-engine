"""Candidate sources. Every source yields batches (lists) of dicts so the engine can pull more on demand.

  csv      postings exported from any job board (columns: metro,company,title,location,posted,job_type,comp,url)
  adzuna   hiring signals from the Adzuna API   (env ADZUNA_APP_ID, ADZUNA_APP_KEY)          -- not tested live
  places   businesses by industry from Google Places (env GOOGLE_PLACES_API_KEY)             -- not tested live
"""
import csv
import datetime as dt
import json
import os
import urllib.parse
import urllib.request

UA = "LeadEngine/0.1 (+business lead research)"


def _http_json(url, data=None, headers=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _posting(company, title, location, posted, job_type, comp, url, metro, city_label):
    return {"kind": "posting", "company": company.strip(), "title": title.strip(), "location": location.strip(),
            "posted": posted, "job_type": (job_type or "").strip().lower(), "comp": comp, "url": url,
            "metro": metro, "city_label": city_label}


def csv_postings(path, cities):
    """cities: list of (city, state). One batch per city so output stays grouped by metro."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for city, state in cities:
        batch = []
        for r in rows:
            if r["metro"].strip().lower() != city.lower():
                continue
            try:
                posted = dt.date.fromisoformat(r["posted"].strip())
            except ValueError:
                posted = None
            url = r.get("url", "")
            if url and not url.startswith("http"):
                url = "https://to.indeed.com/" + url
            batch.append(_posting(r["company"], r["title"], r["location"], posted, r.get("job_type"), r.get("comp"),
                                  url, city, f"{city}, {state}"))
        yield batch


def adzuna_postings(cities, professions, pages=3):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("Set ADZUNA_APP_ID and ADZUNA_APP_KEY (free key at developer.adzuna.com)")
    for city, state in cities:
        for prof in professions:
            for page in range(1, pages + 1):
                q = urllib.parse.urlencode({"app_id": app_id, "app_key": app_key, "results_per_page": 50,
                                            "what": prof, "where": f"{city}, {state}", "max_days_old": 90})
                data = _http_json(f"https://api.adzuna.com/v1/api/jobs/us/search/{page}?{q}")
                batch = []
                for j in data.get("results", []):
                    try:
                        posted = dt.date.fromisoformat(j["created"][:10])
                    except (KeyError, ValueError):
                        posted = None
                    batch.append(_posting((j.get("company") or {}).get("display_name", ""), j.get("title", ""),
                                          (j.get("location") or {}).get("display_name", ""), posted,
                                          (j.get("contract_time") or "").replace("_", "-"), j.get("salary_min"),
                                          j.get("redirect_url", ""), city, f"{city}, {state}"))
                yield batch
                if len(data.get("results", [])) < 50:
                    break


def places_businesses(cities, industry, max_pages=3):
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_PLACES_API_KEY (Places API (New) must be enabled; billed per request)")
    mask = ("places.displayName,places.formattedAddress,places.websiteUri,places.nationalPhoneNumber,"
            "places.rating,places.userRatingCount,nextPageToken")
    for city, state in cities:
        token = None
        for _ in range(max_pages):
            body = {"textQuery": f"{industry} in {city}, {state}", "pageSize": 20}
            if token:
                body["pageToken"] = token
            data = _http_json("https://places.googleapis.com/v1/places:searchText", json.dumps(body).encode(),
                              {"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": mask})
            yield [{"kind": "business", "company": p["displayName"]["text"], "address": p.get("formattedAddress", ""),
                    "website": p.get("websiteUri", ""), "phone": p.get("nationalPhoneNumber", ""),
                    "rating": p.get("rating"), "reviews": p.get("userRatingCount"), "metro": city,
                    "city_label": f"{city}, {state}"} for p in data.get("places", [])]
            token = data.get("nextPageToken")
            if not token:
                break


NJ_CITIES = os.path.join(os.path.dirname(__file__), "data", "nj_cities.txt")
DEFAULT_TAXONOMIES = ["Family Medicine", "Internal Medicine", "Pediatrics", "Obstetrics & Gynecology", "Dermatology",
                      "Ophthalmology", "Orthopaedic Surgery", "Psychiatry"]


def nj_cities():
    with open(NJ_CITIES, encoding="utf-8") as fh:
        return [(ln.strip(), "NJ") for ln in fh if ln.strip() and not ln.startswith("#")]


def county_cities(counties):
    """--county Middlesex --county Somerset -> [(city, 'NJ')...]. Raises with the loaded list if a county is unknown."""
    import json as _json
    with open(os.path.join(os.path.dirname(__file__), "data", "nj_counties.json"), encoding="utf-8") as fh:
        data = {k.lower(): v for k, v in _json.load(fh).items() if not k.startswith("_")}
    out, seen = [], set()
    for c in counties:
        if c.lower() not in data:
            raise SystemExit(f"County {c!r} is not loaded yet. Loaded: {', '.join(k.title() for k in data)}. "
                             "Use --state NJ for the statewide city sweep or add the county to data/nj_counties.json.")
        for city in data[c.lower()]:
            if city not in seen:
                seen.add(city)
                out.append((city, "NJ"))
    return out


def parse_nppes(data, city, state):
    """Pure parser for one NPPES API response page -> provider candidates. Active providers only."""
    out = []
    for r in data.get("results", []):
        basic, kind = r.get("basic", {}), r.get("enumeration_type", "")
        if basic.get("status", "A") != "A":
            continue
        loc = next((a for a in r.get("addresses", []) if a.get("address_purpose") == "LOCATION"), {})
        taxes = r.get("taxonomies") or [{}]
        tax = next((t for t in taxes if t.get("primary")), taxes[0])
        if kind == "NPI-2":
            name = basic.get("organization_name", "")
            first, last = basic.get("authorized_official_first_name", ""), basic.get("authorized_official_last_name", "")
            title = basic.get("authorized_official_title_or_position", "")
        else:
            first, last = basic.get("first_name", ""), basic.get("last_name", "")
            name = " ".join(x for x in (first, last) if x).title() + (f", {basic['credential']}" if basic.get("credential") else "")
            title = basic.get("credential", "")
        if not name.strip():
            continue
        out.append({"kind": "provider", "company": name.strip(), "npi": r.get("number", ""), "npi_type": kind,
                    "sole": (basic.get("sole_proprietor") or "").upper(), "first": first.title(), "last": last.title(),
                    "title": title, "specialty": tax.get("desc", ""), "phone": loc.get("telephone_number", ""),
                    "address": loc.get("address_1", ""), "loc_city": (loc.get("city") or "").title(),
                    "metro": city, "city_label": f"{loc.get('city', city).title()}, {state}"})
    return out


def nppes_providers(cities, taxonomies=None, max_skip=1000):
    """CMS NPI Registry (free, no key). One query per city x taxonomy x type, paged 200 at a time (API cap: skip <= 1000).
    Written from the public API docs; needs npiregistry.cms.hhs.gov reachable. Not tested live."""
    for city, state in cities:
        for tax in (taxonomies or DEFAULT_TAXONOMIES):
            for kind in ("NPI-2", "NPI-1"):
                for skip in range(0, max_skip + 1, 200):
                    q = urllib.parse.urlencode({"version": "2.1", "state": state, "city": city, "enumeration_type": kind,
                                                "taxonomy_description": tax, "limit": 200, "skip": skip})
                    data = _http_json("https://npiregistry.cms.hhs.gov/api/?" + q)
                    if skip == 0 and not data.get("results"):
                        import sys
                        print(f"[nppes] 0 results for {kind} {tax!r} in {city}, {state}", file=sys.stderr)
                    yield parse_nppes(data, city, state)
                    if len(data.get("results", [])) < 200:
                        break


def manual_providers(path, state="NJ"):
    """Hand-assembled practice list (CSV: practice, specialty, city, address, phone, priority, evidence, source).
    priority 1 = a directory says independent / private practice, 2 = standalone name, 3 = individual or uncertain."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    yield [{"kind": "provider", "company": r["practice"].strip(), "npi": "", "npi_type": "NPI-2", "sole": "", "first": "", "last": "",
            "title": "", "specialty": r.get("subspecialty") or r.get("specialty", ""), "phone": r.get("phone", ""), "address": r.get("address", ""),
            "loc_city": r["city"], "metro": r["city"], "city_label": f"{r['city']}, {state}",
            "priority": int(r.get("priority") or 9), "evidence": r.get("evidence", ""), "origin": "Web search (unverified)",
            "origin_note": r.get("source", ""),
            "providers": int(r["providers"]) if (r.get("providers") or "").strip().isdigit() else None,
            "size_override": (r.get("size_override") or "").strip()} for r in rows]
