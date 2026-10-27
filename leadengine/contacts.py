"""Contact discovery from a business's own website: free, key-less, and polite.

Reads the home page and up to `max_pages` pages on the same site that it links as contact / about / team, one request at a time
with a pause, and only where the site's robots.txt allows. It collects what the business itself publishes:
  * email addresses (mailto links, plain text, and the common 'name [at] domain [dot] com' spelling)
  * phone numbers from tel: links
  * LinkedIn company or profile links
It never guesses addresses (no first.last@ patterns) and never probes mail servers. An address found on the business's own
domain is marked 'Risky' (published, not verified); anything else stays 'Unverified'. Run a verifier before sending.

extract(), rank_emails() and robots_allows() are pure so they are tested offline."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.robotparser

from .sources import UA

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
OBFUSCATED = re.compile(r"([A-Za-z0-9._%+-]+)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*([A-Za-z0-9-]+(?:\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*[A-Za-z0-9-]+)+)", re.I)
DOT = re.compile(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", re.I)
HREF = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
TAGS = re.compile(r"<[^>]+>")
CONTACT_WORDS = re.compile(r"contact|about|team|staff|leadership|people|our-?doctors|providers|meet|management|partners", re.I)
JUNK_LOCAL = re.compile(r"^(no-?reply|do-?not-?reply|mailer-daemon|postmaster|abuse|webmaster|example|test|user|email|name|your-?name|privacy|wordpress)$", re.I)
JUNK_DOMAIN = re.compile(r"(example\.(com|org|net)|sentry\.io|wixpress\.com|domain\.com|email\.com|yourdomain|godaddy\.com|squarespace\.com|"
                         r"schema\.org|w3\.org|googleapis\.com|gstatic\.com|cloudflare\.com)$", re.I)
ASSET = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js|ico)$", re.I)
ROLE_ORDER = ["owner", "founder", "ceo", "president", "director", "manager", "office", "partnerships", "partners", "sales", "bd", "business",
              "hello", "contact", "info", "inquiries", "enquiries", "admin", "frontdesk", "appointments", "support",
              "team", "mail", "office", "marketing", "events", "press", "media", "pr", "billing", "accounts", "orders", "hr", "careers", "jobs"]
FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "icloud.com", "me.com", "msn.com", "live.com", "comcast.net",
             "verizon.net", "optonline.net", "protonmail.com"}


def domain_of(url):
    host = urllib.parse.urlsplit(url if re.match(r"https?://", url or "", re.I) else "https://" + (url or "")).hostname or ""
    return host.lower().removeprefix("www.")


def _clean_email(e):
    e = urllib.parse.unquote(e).strip().strip(".,;:").lower()
    e = e.split("?", 1)[0]
    local, _, dom = e.partition("@")
    if not local or not dom or ASSET.search(e) or JUNK_LOCAL.match(local) or JUNK_DOMAIN.search(dom) or re.search(r"\d+x\d*$", local):
        return ""
    return e


def extract(html, base_url):
    """-> {"emails": [...], "phones": [...], "linkedin": [...], "pages": [same-site contact/about urls]} in page order, no repeats."""
    out = {"emails": [], "phones": [], "linkedin": [], "pages": []}
    site = domain_of(base_url)

    def add(kind, v):
        if v and v not in out[kind]:
            out[kind].append(v)

    for href, label in HREF.findall(html):
        h = href.strip()
        low = h.lower()
        if low.startswith("mailto:"):
            add("emails", _clean_email(h[7:]))
        elif low.startswith("tel:"):
            digits = re.sub(r"\D", "", h[4:])
            if len(digits) >= 10:
                add("phones", digits[-10:] if len(digits) == 11 and digits[0] == "1" else digits)
        elif "linkedin.com/company/" in low or "linkedin.com/in/" in low:
            add("linkedin", h.split("?", 1)[0].rstrip("/"))
        elif not low.startswith(("#", "javascript:", "data:")):
            url = urllib.parse.urljoin(base_url, h).split("#", 1)[0]
            if domain_of(url) == site and urllib.parse.urlsplit(url).scheme in ("http", "https") and not ASSET.search(urllib.parse.urlsplit(url).path):
                text = TAGS.sub(" ", label)
                if CONTACT_WORDS.search(urllib.parse.urlsplit(url).path) or CONTACT_WORDS.search(text):
                    add("pages", url)
    text = TAGS.sub(" ", re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.I | re.S))
    text = text.replace("&#64;", "@").replace("&commat;", "@").replace("&#46;", ".")
    for m in EMAIL.finditer(text):
        add("emails", _clean_email(m.group(0)))
    for m in OBFUSCATED.finditer(text):
        add("emails", _clean_email(f"{m.group(1)}@{DOT.sub('.', m.group(2))}"))
    out["emails"] = [e for e in out["emails"] if e]
    return out


def rank_emails(emails, site_domain, first="", last=""):
    """Best address first: the business's own domain over free mail and others; a named person over a role box; role boxes in ROLE_ORDER."""
    first, last = (first or "").lower(), (last or "").lower()

    def key(e):
        local, dom = e.split("@", 1)
        own = dom == site_domain or dom.endswith("." + site_domain)
        named = bool((first and first in local) or (last and len(last) > 2 and last in local))
        role = next((i for i, r in enumerate(ROLE_ORDER) if local == r or local.startswith(r)), None)
        person_like = role is None and re.fullmatch(r"[a-z]+([._-][a-z]+)?", local) is not None
        return (0 if own else 1 if dom in FREE_MAIL else 2, 0 if named else 1 if person_like else 2, role if role is not None else len(ROLE_ORDER))

    return sorted(dict.fromkeys(emails), key=key)


def robots_allows(robots_txt, url, agent=UA):
    rp = urllib.robotparser.RobotFileParser()
    rp.parse((robots_txt or "").splitlines())
    return rp.can_fetch(agent, url)


def _fetch(url, timeout=12):
    from .audit import fetch
    return fetch(url, timeout)


class ContactFinder:
    """Looks contacts up on each lead's own website, with a disk cache and a cap on sites per run. Never raises on a bad site."""

    def __init__(self, state_dir=".leadengine", max_sites=100, max_pages=3, delay=1.0, fetcher=None, sleep=time.sleep):
        self.cache_path = os.path.join(state_dir, "contacts_cache.json")
        os.makedirs(state_dir, exist_ok=True)
        try:
            with open(self.cache_path, encoding="utf-8") as fh:
                self.cache = json.load(fh)
        except (OSError, ValueError):
            self.cache = {}
        self.max_sites, self.max_pages, self.delay = max_sites, max_pages, delay
        self.fetcher, self.sleep = fetcher or _fetch, sleep
        self.sites, self.stopped = 0, ""

    def _robots(self, root):
        try:
            _, txt = self.fetcher(root + "/robots.txt")
            return txt
        except urllib.error.HTTPError as exc:
            return "User-agent: *\nDisallow: /" if exc.code in (401, 403) else ""
        except Exception:
            return None                                  # cannot tell what the site allows: do not crawl it

    def find(self, website, first="", last=""):
        """-> {"email", "estatus", "phone", "linkedin", "page", "note"}; blanks when nothing was found or the site was skipped."""
        site = domain_of(website)
        blank = {"email": "", "estatus": "", "phone": "", "linkedin": "", "page": "", "note": ""}
        if not site:
            return blank
        if site in self.cache:
            return self.cache[site]
        if self.sites >= self.max_sites:
            self.stopped = f"per-run cap of {self.max_sites} sites reached"
            return blank
        self.sites += 1
        home = website if re.match(r"https?://", website, re.I) else "https://" + website
        root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(home))
        robots = self._robots(root)
        if robots is None:
            return {**blank, "note": "contact lookup skipped: site unreachable"}
        found = {"emails": [], "phones": [], "linkedin": []}
        queue, seen, page_with_email = [home], set(), ""
        while queue and len(seen) < 1 + self.max_pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            if not robots_allows(robots, url):
                continue
            if len(seen) > 1:
                self.sleep(self.delay)
            try:
                final, html = self.fetcher(url)
            except Exception:
                continue
            got = extract(html, final)
            if got["emails"] and not page_with_email:
                page_with_email = final
            for k in found:
                found[k] += [v for v in got[k] if v not in found[k]]
            queue += [p for p in got["pages"] if p not in seen and p not in queue]
        emails = rank_emails(found["emails"], site, first, last)
        best = emails[0] if emails else ""
        own = bool(best) and (best.split("@", 1)[1] == site or best.split("@", 1)[1].endswith("." + site))
        result = {"email": best, "estatus": ("Risky" if own else "Unverified") if best else "",
                  "phone": found["phones"][0] if found["phones"] else "",
                  "linkedin": next((u for u in found["linkedin"] if "/company/" in u), found["linkedin"][0] if found["linkedin"] else ""),
                  "page": page_with_email, "note": (f"{len(emails)} address(es) published on the site" if emails else "no address published on the site")}
        self.cache[site] = result
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(self.cache, fh)
        return result
