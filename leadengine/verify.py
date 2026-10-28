"""Accuracy checks for a lead list: what each field claims, checked as far as free sources allow.

Offline checks (always run, no network): email syntax, role and free-mail addresses, phone numbers (North American numbering rules),
NPI check digits, website address shape, email domain against website domain, duplicates across the list.
Network checks (free, no key; each skipped cleanly when the network is closed):
  * the email domain has mail servers (DNS over HTTPS, MX then A records); a domain that does not exist makes the address Invalid
  * the website answers, is not a parked or for-sale page, and does not redirect to another business's domain
  * an NPI is active in the NPPES registry and the name on file matches
Paid verification (only with your own key and an explicit flag): ZeroBounce or NeverBounce check each mailbox; only they can mark an address Valid.

Nothing here guesses data. A check that could not run says "not checked", never "ok"."""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from .contacts import FREE_MAIL, domain_of
from .filters import norm_name
from .keys import dedupe_key
from .mailer import EMAIL

ROLE = re.compile(r"^(info|office|contact|hello|admin|frontdesk|front\.desk|reception|appointments?|support|sales|billing|team|mail|"
                  r"inquiries|enquiries|marketing|hr|careers|jobs|noreply|no-reply)([._-]?\d*)?$", re.I)
DISPOSABLE = {"mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
              "getnada.com", "dispostable.com", "maildrop.cc"}
PARKED = re.compile(r"domain (is )?(for sale|may be for sale)|buy this domain|this domain is parked|parked free|domain parking|"
                    r"godaddy\.com/domainsearch|sedo\.com|dan\.com|hugedomains|afternic|website coming soon|under construction", re.I)
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD "
             "TN TX UT VT VA WA WV WI WY PR VI GU AS MP".split())
NOT_CHECKED = "not checked"


# ---- offline checks ------------------------------------------------------------
def email_check(email):
    """-> (status or "", issues). status is "Invalid" when the address cannot work; otherwise "" (leave the status as it is)."""
    e = (email or "").strip()
    if not e:
        return "", ["no email"]
    if not EMAIL.match(e) or ".." in e or e.split("@")[0].startswith(".") or e.split("@")[0].endswith("."):
        return "Invalid", ["email is not a valid address"]
    local, dom = e.lower().split("@", 1)
    issues = []
    if dom in DISPOSABLE:
        return "Invalid", ["disposable mailbox"]
    if ROLE.match(local):
        issues.append("role address (reaches a shared inbox, not a person)")
    if dom in FREE_MAIL:
        issues.append("free mail address")
    return "", issues


def phone_check(phone):
    """North American Numbering Plan rules. -> (formatted "(732) 555-0199" or "", issues)."""
    raw = (phone or "").strip()
    if not raw:
        return "", ["no phone"]
    d = re.sub(r"\D", "", raw.split("x")[0].split("ext")[0])
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    if len(d) != 10:
        return "", [f"phone {raw!r} is not a 10-digit US or Canadian number"]
    area, exch, line = d[:3], d[3:6], d[6:]
    issues = []
    if area[0] in "01" or area[1:] == "11":
        issues.append(f"area code {area} does not exist")
    if exch[0] in "01" or exch[1:] == "11":
        issues.append(f"exchange {exch} is not a valid local number")
    if exch == "555" and line.startswith("01"):
        issues.append("555-01xx is a fictional number")
    if len(set(d)) == 1:
        issues.append("phone is a placeholder")
    return ("" if issues else f"({area}) {exch}-{line}"), issues


def npi_valid(npi):
    """The NPI check digit (Luhn over '80840' + the first nine digits)."""
    d = re.sub(r"\D", "", npi or "")
    if len(d) != 10:
        return False
    total = 0
    for i, ch in enumerate(reversed("80840" + d[:9])):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return (10 - total % 10) % 10 == int(d[9])


def url_check(url):
    u = (url or "").strip()
    if not u:
        return ["no website"]
    full = u if re.match(r"https?://", u, re.I) else "https://" + u
    host = urllib.parse.urlsplit(full).hostname or ""
    if not re.fullmatch(r"([a-z0-9-]+\.)+[a-z]{2,24}", host.lower()):
        return [f"website {u!r} is not a valid address"]
    if re.search(r"(facebook|instagram|yelp|linkedin|google|healthgrades|zocdoc|vitals|webmd|bbb|angi|thumbtack|yellowpages)\.com$", host, re.I):
        return [f"website is a listing on {host}, not the business's own site"]
    return []


def offline(row):
    """-> {"email_status", "phone", "issues", "checks"} from the row alone."""
    issues, checks = [], {}
    status, e_issues = email_check(row.get("Email"))
    issues += e_issues
    checks["email"] = "invalid" if status == "Invalid" else ("none" if not row.get("Email") else "syntax ok")
    phone, p_issues = phone_check(row.get("Phone"))
    issues += p_issues
    checks["phone"] = "valid" if phone else ("none" if not row.get("Phone") else "invalid")
    w_issues = url_check(row.get("Website"))
    issues += [i for i in w_issues if i != "no website"]
    if row.get("NPI"):
        ok = npi_valid(row["NPI"])
        checks["npi"] = "check digit ok" if ok else "invalid"
        if not ok:
            issues.append(f"NPI {row['NPI']} fails its check digit")
    st = (row.get("State") or "").strip().upper()
    if st and st not in STATES:
        issues.append(f"state {st!r} is not a US state code")
    e, w = (row.get("Email") or "").lower(), row.get("Website") or ""
    if "@" in e and w and not w_issues:
        ed, wd = e.split("@", 1)[1], domain_of(w)
        if ed not in FREE_MAIL and ed != wd and not ed.endswith("." + wd) and not wd.endswith("." + ed):
            issues.append(f"email domain {ed} differs from the website {wd}")
    name = row.get("Company") or ""
    if name and name.isupper() and len(name) > 4:
        issues.append("company name is in capitals (registry style), check how the business writes it")
    first = (row.get("First Name") or "").strip()
    if first and (ROLE.match(first.lower()) or not re.fullmatch(r"[A-Za-z][A-Za-z'.\- ]{0,30}", first)):
        issues.append(f"first name {first!r} does not look like a person's name")
    return {"email_status": status, "phone": phone, "issues": issues, "checks": checks}


def duplicates(rows):
    """-> {row index: "duplicate of row N (same ...)"} for rows that repeat an earlier one by key, email or phone."""
    seen, out = {}, {}
    for i, r in enumerate(rows):
        keys = [("lead key", r.get("Lead Key") or dedupe_key(r.get("Website", ""), r.get("Company", ""), r.get("City", "")))]
        if (r.get("Email") or "").strip():
            keys.append(("email", r["Email"].strip().lower()))
        p = re.sub(r"\D", "", r.get("Phone") or "")[-10:]
        if len(p) == 10:
            keys.append(("phone", p))
        keys.append(("name and city", f"{norm_name(r.get('Company', ''))}|{(r.get('City') or '').lower()}"))
        for kind, k in keys:
            if k and k in seen:
                out[i] = f"duplicate of row {seen[k] + 2} (same {kind})"
                break
        for kind, k in keys:
            seen.setdefault(k, i)
    return out


# ---- network checks (injected opener so tests run offline) ------------------------------------
UA = "LeadEngine verify (+https://github.com/punjabitaz-ctrl/lead-engine)"


def _get_json(url, opener, timeout=15):
    with opener(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/dns-json"}), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Checker:
    """Network checks with a per-run cache. Any network failure gives "not checked", never a verdict."""
    DOH = "https://dns.google/resolve?"

    def __init__(self, opener=None, fetch=None, today=None, nppes_url="https://npiregistry.cms.hhs.gov/api/?"):
        self.open = opener or urllib.request.urlopen
        self._fetch = fetch
        self.today = today or dt.date.today()
        self.nppes_url = nppes_url
        self.mx_cache, self.site_cache = {}, {}
        self.failures = 0

    def mail_domain(self, domain):
        """-> "ok" (MX or A records), "no mail servers", "domain does not exist", or NOT_CHECKED."""
        if domain in self.mx_cache:
            return self.mx_cache[domain]
        verdict = NOT_CHECKED
        try:
            mx = _get_json(self.DOH + urllib.parse.urlencode({"name": domain, "type": "MX"}), self.open)
            if mx.get("Status") == 3:
                verdict = "domain does not exist"
            elif any(a.get("type") == 15 for a in mx.get("Answer", [])):
                verdict = "ok"
            else:
                a = _get_json(self.DOH + urllib.parse.urlencode({"name": domain, "type": "A"}), self.open)
                verdict = "ok" if any(x.get("type") == 1 for x in a.get("Answer", [])) else "no mail servers"
        except (OSError, ValueError, urllib.error.URLError):
            self.failures += 1
        self.mx_cache[domain] = verdict
        return verdict

    def website(self, url):
        """-> ("live" | "parked" | "redirects to <domain>" | "down" | NOT_CHECKED, final url)."""
        if url in self.site_cache:
            return self.site_cache[url]
        from . import audit
        fetch = self._fetch or audit.fetch
        try:
            final, html = fetch(url)
        except urllib.error.HTTPError as exc:
            res = ("down" if exc.code in (404, 410) or exc.code >= 500 else NOT_CHECKED, "")
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            res = ("down" if re.search(r"Name or service not known|nodename nor servname|getaddrinfo failed|No address associated", reason) else NOT_CHECKED, "")
            if res[0] == NOT_CHECKED:
                self.failures += 1
        except Exception:
            self.failures += 1
            res = (NOT_CHECKED, "")
        else:
            a, b = domain_of(url), domain_of(final)
            if PARKED.search(html[:20000]) and len(re.sub(r"<[^>]+>", " ", html)) < 20000:
                res = ("parked", final)
            elif b and a != b and not b.endswith("." + a) and not a.endswith("." + b):
                res = (f"redirects to {b}", final)
            else:
                res = ("live", final)
        self.site_cache[url] = res
        return res

    def npi(self, npi, company="", last=""):
        """-> ("active" | "not found" | "name differs: <registry name>", issues) from the NPPES registry."""
        try:
            data = _get_json(self.nppes_url + urllib.parse.urlencode({"version": "2.1", "number": re.sub(r"\D", "", npi)}), self.open)
        except (OSError, ValueError, urllib.error.URLError):
            self.failures += 1
            return NOT_CHECKED
        res = data.get("results") or []
        if not res:
            return "not found"
        b = res[0].get("basic", {})
        if b.get("status") and b["status"] != "A":
            return "deactivated"
        names = {norm_name(b.get(k, "")) for k in ("organization_name", "name") if b.get(k)}
        names |= {norm_name(b.get("last_name", ""))} if b.get("last_name") else set()
        target = {norm_name(company), norm_name(last)} - {""}
        if names and target and not any(t and (t in n or n in t) for t in target for n in names):
            return "name differs: " + (b.get("organization_name") or f"{b.get('first_name', '')} {b.get('last_name', '')}").strip()
        return "active"


# ---- paid verifiers (your key, your account) ----------------------------------------------
VERIFIERS = {
    "zerobounce": {"env": "ZEROBOUNCE_API_KEY",
                   "url": lambda key, e: "https://api.zerobounce.net/v2/validate?" + urllib.parse.urlencode({"api_key": key, "email": e, "ip_address": ""}),
                   "read": lambda d: {"valid": "Valid", "invalid": "Invalid", "spamtrap": "Invalid", "abuse": "Invalid",
                                      "do_not_mail": "Invalid", "catch-all": "Risky", "unknown": "Risky"}.get(str(d.get("status", "")).lower(), "Risky")},
    "neverbounce": {"env": "NEVERBOUNCE_API_KEY",
                    "url": lambda key, e: "https://api.neverbounce.com/v4/single/check?" + urllib.parse.urlencode({"key": key, "email": e}),
                    "read": lambda d: {"valid": "Valid", "invalid": "Invalid", "disposable": "Invalid", "catchall": "Risky",
                                       "unknown": "Risky"}.get(str(d.get("result", "")).lower(), "Risky")},
}


class PaidVerifier:
    """One API call per address, up to `limit` a run. Results are cached on disk so an address is never paid for twice."""

    def __init__(self, name, limit, state_dir=".leadengine", opener=None):
        if name not in VERIFIERS:
            raise SystemExit(f"Unknown verifier {name!r}; choose {', '.join(VERIFIERS)}")
        self.v = VERIFIERS[name]
        self.key = os.environ.get(self.v["env"])
        if not self.key:
            raise SystemExit(f"{self.v['env']} is not set. Add your own key to the environment on your computer (never in the repo). Nothing was checked.")
        self.name, self.limit, self.used, self.open = name, limit, 0, opener or urllib.request.urlopen
        self.cache_path = os.path.join(state_dir, f"verify_{name}.json")
        os.makedirs(state_dir, exist_ok=True)
        try:
            with open(self.cache_path, encoding="utf-8") as fh:
                self.cache = json.load(fh)
        except (OSError, ValueError):
            self.cache = {}

    def check(self, email):
        e = email.strip().lower()
        if e in self.cache:
            return self.cache[e]
        if self.used >= self.limit:
            return ""
        try:
            data = _get_json(self.v["url"](self.key, e), self.open, timeout=30)
        except (OSError, ValueError, urllib.error.URLError):
            return ""
        self.used += 1
        status = self.v["read"](data)
        self.cache[e] = status
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(self.cache, fh)
        return status


# ---- confidence -----------------------------------------------------------------
PENALTY = [("email is not a valid address", 30), ("disposable mailbox", 30), ("no mail servers", 30), ("domain does not exist", 35),
           ("no email", 15), ("role address", 5), ("not a 10-digit", 15), ("does not exist", 10), ("not a valid local number", 10),
           ("fictional number", 15), ("placeholder", 15), ("no phone", 5), ("website is down", 20), ("website is parked", 25),
           ("redirects to", 15), ("not the business's own site", 5), ("fails its check digit", 30), ("NPI is not active", 40),
           ("NPI not found", 30), ("registry name differs", 15), ("duplicate of row", 10), ("differs from the website", 5),
           ("not verified for", 10), ("does not look like a person", 5)]


def confidence(issues, email_status):
    """A plain heuristic, 0-100: start at 100 and take off points per issue. It ranks rows for checking; it is not a probability."""
    score = 100
    for text in issues:
        score -= next((p for k, p in PENALTY if k in text), 0)
    score -= {"Valid": 0, "Risky": 5, "Invalid": 30}.get(email_status, 10 if email_status else 0)
    return max(0, min(100, score))
