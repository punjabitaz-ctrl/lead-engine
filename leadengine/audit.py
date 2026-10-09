"""Free, key-less website check. analyze_html() is pure so it can be tested offline."""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request

from .sources import UA

VIEWPORT = re.compile(r"<meta[^>]+name=[\"']viewport[\"']", re.I)
COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)[^0-9<]{0,40}((?:19|20)\d{2})(?:\s*[-–]\s*((?:19|20)\d{2}))?", re.I)


def analyze_html(html, url, today=None, stale_years=3):
    """Returns (outdated: bool, notes: list[str])."""
    today = today or dt.date.today()
    notes = []
    if not VIEWPORT.search(html):
        notes.append("no mobile viewport tag")
    if url.lower().startswith("http://"):
        notes.append("not served over HTTPS")
    years = []
    for m in COPYRIGHT.finditer(html):
        years.append(int(m.group(2) or m.group(1)))
    if years and today.year - max(years) >= stale_years:
        notes.append(f"footer still says {max(years)}")
    return bool(notes), notes


def fetch(url, timeout=12):
    if not re.match(r"https?://", url, re.I):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.read(400_000).decode("utf-8", "ignore")


def audit_site(url):
    """Returns dict(outdated='Y'|'N'|'', note=str). Never raises: unreachable sites return blanks."""
    try:
        final, html = fetch(url)
    except Exception as exc:  # network blocked, DNS, TLS, 4xx/5xx
        return {"outdated": "", "note": f"audit failed: {type(exc).__name__}"}
    outdated, notes = analyze_html(html, final)
    return {"outdated": "Y" if outdated else "N", "note": "; ".join(notes)}


def psi_score(url, api_key, timeout=60):
    """Mobile performance score 0-100 from the free PageSpeed Insights API, or None."""
    q = urllib.parse.urlencode({"url": url, "strategy": "mobile", "category": "performance", "key": api_key})
    try:
        req = urllib.request.Request("https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + q,
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return round(data["lighthouseResult"]["categories"]["performance"]["score"] * 100)
    except Exception:
        return None
