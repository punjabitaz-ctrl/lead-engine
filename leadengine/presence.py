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


class PlacesChecker:
    """Google Places (New) text search with a disk cache and hard spend caps (per run and per calendar month).
    Not tested live. Each lookup requests websiteUri/phone/rating fields, which Google bills at its Enterprise rate."""

    def __init__(self, state_dir=".leadengine", run_cap=200, monthly_cap=1000, today=None):
        import datetime as dt
        self.cache_path = os.path.join(state_dir, "presence_cache.json")
        self.usage_path = os.path.join(state_dir, "places_usage.json")
        self.month = (today or dt.date.today()).strftime("%Y-%m")
        self.run_cap, self.monthly_cap, self.calls, self.stopped = run_cap, monthly_cap, 0, ""
        self.cache = self._load(self.cache_path)
        self.usage = self._load(self.usage_path)
        os.makedirs(state_dir, exist_ok=True)

    @staticmethod
    def _load(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _save(self):
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(self.cache, fh)
        with open(self.usage_path, "w", encoding="utf-8") as fh:
            json.dump(self.usage, fh)

    def check(self, name, city, state, phone=""):
        ck = f"{norm_name(name)}|{city.lower()}|{state}"
        if ck in self.cache:
            return self.cache[ck]
        if self.calls >= self.run_cap:
            self.stopped = f"per-run cap of {self.run_cap} lookups reached"
            return None
        if self.usage.get(self.month, 0) >= self.monthly_cap:
            self.stopped = f"monthly cap of {self.monthly_cap} lookups reached"
            return None
        row = _places_lookup(name, city, state, phone)
        if row is None:                       # failed call: do not cache, do not count as a confirmed gap
            return None
        self.calls += 1
        self.usage[self.month] = self.usage.get(self.month, 0) + 1
        self.cache[ck] = row
        self._save()
        return row

    def cost_note(self, per_1000=35.0, free_monthly=1000):
        used = self.usage.get(self.month, 0)
        billable = max(0, used - free_monthly)
        return (f"{self.calls} Places lookups this run, {used} this month "
                f"(~${billable * per_1000 / 1000:.2f} billable if Google's listed ${per_1000:.0f}/1,000 and "
                f"{free_monthly} free/month still apply: verify current pricing)")


def _places_lookup(name, city, state, phone=""):
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
