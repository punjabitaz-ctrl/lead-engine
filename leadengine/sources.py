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
