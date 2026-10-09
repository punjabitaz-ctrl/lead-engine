"""Web-presence check for local businesses. Absence of evidence is the lead signal here, so every 'N' must be earned:
either imported from a human check (CSV) or from a Places lookup that found no matching listing."""
import csv
import difflib
import json
import os
import re
import urllib.parse

from .filters import norm_name
from .sources import _http_json


def load_presence(path):
    """CSV columns: npi or company, has_website (Y/N), has_gbp (Y/N), reviews (optional)."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            key = (r.get("npi") or "").strip() or norm_name(r.get("company", ""))
            out[key] = {"hasweb": (r.get("has_website") or "").strip().upper()[:1],
                        "hasgbp": (r.get("has_gbp") or "").strip().upper()[:1],
                        "reviews": int(r["reviews"]) if (r.get("reviews") or "").strip().isdigit() else None}
    return out


def check_links(name, city, state):
    """Two links for a 30-second human check when no Places key is available."""
    q = urllib.parse.quote_plus(f'"{name}" {city} {state}')
    return f"https://www.google.com/search?q={q} | https://www.google.com/maps/search/{q}"


def _digits(p):
    return re.sub(r"\D", "", p or "")[-10:]


def check_places(name, city, state, phone=""):
    """Google Places (New) text search. Returns dict(hasweb, hasgbp, reviews) or None if the call fails.
    Not tested live. No match is reported as N/N only when the search returned nothing similar."""
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        return None
    body = json.dumps({"textQuery": f"{name} {city} {state}", "pageSize": 5}).encode()
    try:
        data = _http_json("https://places.googleapis.com/v1/places:searchText", body,
                          {"Content-Type": "application/json", "X-Goog-Api-Key": key,
                           "X-Goog-FieldMask": "places.displayName,places.websiteUri,places.nationalPhoneNumber,places.userRatingCount"})
    except Exception:
        return None
    for p in data.get("places", []):
        same_phone = phone and _digits(phone) == _digits(p.get("nationalPhoneNumber"))
        similar = difflib.SequenceMatcher(None, norm_name(name), norm_name(p["displayName"]["text"])).ratio() >= 0.75
        if same_phone or similar:
            return {"hasweb": "Y" if p.get("websiteUri") else "N", "hasgbp": "Y", "reviews": p.get("userRatingCount") or 0}
    return {"hasweb": "N", "hasgbp": "N", "reviews": None}
