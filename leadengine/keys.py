"""Must stay identical to the Dedupe Key and Tracked Link formulas in lead-engine-template.xlsx."""
from urllib.parse import quote


def dedupe_key(website, company, city):
    if not website:
        return f"{company.strip().lower()}|{city.strip().lower()}"
    x = website.strip().lower()
    for junk in ("https://", "http://", "www."):
        x = x.replace(junk, "")
    return x.split("/", 1)[0]


def tracked_link(base, key, to, mode="plain"):
    """plain: the link as-is. utm: your own URL plus utm tags (pair with tracker/track.js; best deliverability).
    redirect: click-logging redirect through the tracker function (a third-party domain in the link; can hurt deliverability)."""
    if mode == "utm":
        sep = "&" if "?" in to else "?"
        return f"{to}{sep}utm_source=leadengine&utm_content={quote(key, safe='')}"
    if mode == "redirect" and base:
        return f"{base.rstrip('/')}/t?l={quote(key, safe='')}&to={quote(to, safe='')}"
    return to
