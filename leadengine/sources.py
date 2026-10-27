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


class SpendCap:
    """Counts billed requests per run and per calendar month in a small JSON file, so a wide sweep cannot run up a surprise bill.
    The same file is shared with the presence checker (state_dir/places_usage.json)."""

    def __init__(self, usage_path=None, run_cap=200, monthly_cap=1000, today=None):
        self.path, self.run_cap, self.monthly_cap, self.calls, self.stopped = usage_path, run_cap, monthly_cap, 0, ""
        self.month = (today or dt.date.today()).strftime("%Y-%m")
        self.usage = {}
        if usage_path and os.path.exists(usage_path):
            try:
                with open(usage_path, encoding="utf-8") as fh:
                    self.usage = json.load(fh)
            except ValueError:
                self.usage = {}

    def take(self):
        if self.calls >= self.run_cap:
            self.stopped = f"per-run cap of {self.run_cap} Places requests reached"
            return False
        if self.usage.get(self.month, 0) >= self.monthly_cap:
            self.stopped = f"monthly cap of {self.monthly_cap} Places requests reached"
            return False
        self.calls += 1
        self.usage[self.month] = self.usage.get(self.month, 0) + 1
        if self.path:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.usage, fh)
        return True


def places_businesses(cities, industry, max_pages=3, cap=None, fetch=None):
    """industry: one text-search phrase, or a list of phrases (each searched in every city). cap: a SpendCap; the sweep stops,
    and says so on stderr, when it is reached."""
    import sys
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_PLACES_API_KEY (Places API (New) must be enabled; billed per request)")
    fetch = fetch or _http_json
    mask = ("places.displayName,places.formattedAddress,places.websiteUri,places.nationalPhoneNumber,"
            "places.rating,places.userRatingCount,nextPageToken")
    queries = [industry] if isinstance(industry, str) else list(industry)
    for city, state in cities:
        for query in queries:
            token = None
            for _ in range(max_pages):
                body = {"textQuery": f"{query} in {city}, {state}", "pageSize": 20}
                if token:
                    body["pageToken"] = token
                if cap and not cap.take():
                    print(f"[places] stopped: {cap.stopped}. Raise --max-places-calls / --monthly-places-cap to continue.", file=sys.stderr)
                    return
                data = fetch("https://places.googleapis.com/v1/places:searchText", json.dumps(body).encode(),
                                  {"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": mask})
                yield [{"kind": "business", "company": p["displayName"]["text"], "address": p.get("formattedAddress", ""),
                        "website": p.get("websiteUri", ""), "phone": p.get("nationalPhoneNumber", ""),
                        "rating": p.get("rating"), "reviews": p.get("userRatingCount"), "metro": city,
                        "city_label": f"{city}, {state}"} for p in data.get("places", [])]
                token = data.get("nextPageToken")
                if not token:
                    break


DEFAULT_TAXONOMIES = ["Family Medicine", "Internal Medicine", "Pediatrics", "Obstetrics & Gynecology", "Dermatology",
                      "Ophthalmology", "Orthopaedic Surgery", "Psychiatry"]


def nj_cities():
    from . import geo
    return geo.statewide("NJ")


def county_cities(counties, state="NJ"):
    """--county Middlesex --county Somerset -> [(city, 'NJ')...]. Raises with the loaded list if a county is unknown."""
    from . import geo
    return geo.county_cities(counties, state)


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
                    where = {"postal_code": city} if city.isdigit() else {"city": city}      # a 5-digit "city" is a ZIP code
                    q = urllib.parse.urlencode({"version": "2.1", "state": state, **where, "enumeration_type": kind,
                                                "taxonomy_description": tax, "limit": 200, "skip": skip})
                    data = _http_json("https://npiregistry.cms.hhs.gov/api/?" + q)
                    if skip == 0 and not data.get("results"):
                        import sys
                        print(f"[nppes] 0 results for {kind} {tax!r} in {city}, {state}", file=sys.stderr)
                    yield parse_nppes(data, city, state)
                    if len(data.get("results", [])) < 200:
                        break


def manual_providers(path, state="NJ"):  # state: two-letter code written on each row
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


COMPANY_COLUMNS = ["company", "website", "city", "state", "country", "industry", "employees", "signal", "signal_date", "evidence",
                   "first", "last", "title", "email", "email_status", "linkedin", "phone", "priority", "source"]


def company_list(path, state=""):
    """Any company list you are allowed to use: a CRM or Apollo/Sales Navigator export, a trade-show exhibitor list, an accelerator
    cohort, your own research. Only `company` is required; see COMPANY_COLUMNS. `signal` is the reason to contact them now (for example
    'Hiring: US channel manager', 'Opened a US office', 'Exhibiting at CES 2027'); a signal mentioning hiring counts as a hiring signal,
    anything else as an expansion signal. `signal_date` (YYYY-MM-DD) drives freshness. One batch per file."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if rows and "company" not in rows[0]:
        raise SystemExit(f"{path}: needs a 'company' column (optional: {', '.join(COMPANY_COLUMNS[1:])})")
    batch = []
    for r in rows:
        g = lambda k: (r.get(k) or "").strip()
        if not g("company"):
            continue
        try:
            sigdate = dt.date.fromisoformat(g("signal_date")) if g("signal_date") else None
        except ValueError:
            sigdate = None
        city, st = g("city"), g("state") or state
        batch.append({"kind": "company", "company": g("company"), "website": g("website"), "phone": g("phone"), "industry": g("industry"),
                      "employees": g("employees"), "signal": g("signal"), "signal_date": sigdate, "evidence": g("evidence"),
                      "first": g("first"), "last": g("last"), "title": g("title"), "email": g("email"), "estatus": g("email_status"),
                      "linkedin": g("linkedin"), "country": g("country"), "address": "",
                      "priority": int(g("priority")) if g("priority").isdigit() else 9, "origin": g("source") and f"List: {g('source')}" or "",
                      "source_note": g("source"), "metro": city, "city_label": f"{city or 'Unknown'}, {st or g('country') or '-'}"})
    yield batch
