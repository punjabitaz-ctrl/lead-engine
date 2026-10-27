"""Sending email: compliant messages, pluggable providers, caps, pacing and a send ledger.

Nothing here decides who gets an email. mailing.py (marketing mailings) and batch.py (sequence email 1) pick the recipients,
show a person the batch and record their approval; this module only sends what they hand it, and refuses when:
  * the sender block is incomplete (CAN-SPAM: accurate From, a physical postal address, a working opt-out)
  * the subject could mislead (Re:/Fwd: on a first email, all capitals, "invoice", "final notice" and the like)
  * it is outside the send window, the day's cap (with warm-up) is used, or recent bounces are too high

Providers (config mail.provider, or --provider):
  file   writes each message to an outbox folder as .eml and sends nothing (the dry run)
  smtp   any SMTP server: Gmail or Google Workspace with an app password, Outlook, Zoho, or a relay like Amazon SES or SendGrid SMTP
  gmail  the Gmail API with your own OAuth client (leadengine mail auth gmail)
Add another (an HTTP API such as SES or SendGrid) with register("name", factory); a provider needs account() and send(msg) -> id.

Credentials never live in the repo: environment variables, or files in ~/.config/leadengine/ (LEADENGINE_CONFIG_DIR), see docs/EMAIL_SENDING.md.
Every attempt goes to <root>/_mail/ledger.csv, shared by all campaigns so a sender's daily cap is counted across them."""
import base64
import csv
import datetime as dt
import email.utils
import hashlib
import json
import os
import random
import re
import secrets
import smtplib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from . import campaign

EMAIL = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}$")
OPT_OUT_LINE = re.compile(r"no thanks|unsubscribe|opt out|stop", re.I)
MISLEADING = re.compile(r"^\s*(re|fwd?|aw|tr)\s*:|\b(invoice|payment due|past due|final notice|account (suspended|locked|closed)|"
                        r"order confirm|receipt|your (order|package|refund)|urgent|act now|winner|you('ve| have) won)\b", re.I)
LEDGER_FIELDS = ["Time", "Date", "From", "To", "Campaign", "Mailing", "Batch", "Lead Key", "Company", "Subject", "Status", "Provider",
                 "Message ID", "Error"]
SENT = "sent"


class SetupError(SystemExit):
    """Credentials or settings are missing: nothing was sent."""


class Permanent(Exception):
    """The server refused this recipient (bad address, mailbox gone): log it as a bounce and suppress the address."""


class Temporary(Exception):
    """Try again later (busy server, network): the recipient stays unsent and is picked up by the next run."""


class Fatal(Exception):
    """Stop the whole batch (bad login, sending limit reached, From not allowed)."""


# ---- settings ----------------------------------------------------------------
def config_dir():
    return os.environ.get("LEADENGINE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".config", "leadengine")


def unsubscribe_address(cfg):
    m = cfg["mail"]
    return (m.get("unsubscribe_email") or cfg["sender"].get("reply_email") or m.get("from_email") or "").strip()


def sender_problems(cfg):
    """Blocking problems with who the mail says it is from and how to opt out."""
    s, m, out = cfg["sender"], cfg["mail"], []
    for k in ("name", "business", "address"):
        v = str(s.get(k, "")).strip()
        if not v or campaign.PLACEHOLDER.search(v):
            out.append(f"config.json sender.{k} is empty or still a [placeholder]" + (" (CAN-SPAM needs your physical postal address)" if k == "address" else ""))
    if not EMAIL.match((m.get("from_email") or "").strip()):
        out.append("config.json mail.from_email is not set: use the address you send from (the account you log in with)")
    for k in ("reply_email", ):
        v = (s.get(k) or "").strip()
        if v and not EMAIL.match(v):
            out.append(f"config.json sender.{k} is not an email address")
    if not EMAIL.match(unsubscribe_address(cfg)):
        out.append("no address to receive opt-outs: set mail.unsubscribe_email or sender.reply_email")
    url = (m.get("unsubscribe_url") or "").strip()
    if url and not url.startswith("https://"):
        out.append("mail.unsubscribe_url must be an https:// link (or leave it empty to use reply and email opt-out only)")
    return out


def subject_problems(subject):
    s = (subject or "").strip()
    if not s:
        return ["empty subject"]
    out = []
    if MISLEADING.search(s):
        out.append(f"subject could mislead ({MISLEADING.search(s).group(0).strip()!r}); say plainly what the email is about")
    letters = [c for c in s if c.isalpha()]
    if len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        out.append("subject is mostly capital letters")
    if re.search(r"[!?$]{2,}", s):
        out.append("subject has repeated ! ? or $")
    return out


def body_problems(body, cfg):
    """For drafts that carry their own footer (sequence email 1): it must have the opt-out line and the postal address."""
    out = []
    if not OPT_OUT_LINE.search(body or ""):
        out.append("no opt-out line in the email")
    addr = str(cfg["sender"].get("address", "")).strip()
    if addr and addr not in (body or ""):
        out.append("the sender's postal address is not in the email")
    return out


def footer(cfg):
    """The compliance block every marketing email ends with."""
    s, m = cfg["sender"], cfg["mail"]
    unsub = unsubscribe_address(cfg)
    lines = ["--", f"{s['name']}, {s['business']}", s["address"]]
    if m.get("ad_disclosure", True):
        lines.append(f"This is a marketing email from {s['business']}.")
    how = f'To stop getting these emails, reply "no thanks" or email {unsub} with "unsubscribe" in the subject'
    if m.get("unsubscribe_url"):
        how += f", or use {m['unsubscribe_url']}"
    lines.append(how + ". I'll take you off the list right away.")
    return "\n".join(lines)


def build(cfg, to, subject, body):
    """-> EmailMessage with accurate From, Reply-To and List-Unsubscribe headers. Plain text only (better delivered, nothing hidden)."""
    s, m = cfg["sender"], cfg["mail"]
    frm = m["from_email"].strip()
    msg = EmailMessage()
    msg["From"] = email.utils.formataddr((s["name"], frm))
    msg["To"] = to
    msg["Subject"] = subject
    reply = (s.get("reply_email") or "").strip()
    if reply and reply.lower() != frm.lower():
        msg["Reply-To"] = reply
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=frm.split("@", 1)[1])
    unsub = [f"<mailto:{unsubscribe_address(cfg)}?subject=unsubscribe>"]
    if m.get("unsubscribe_url"):
        unsub.append(f"<{m['unsubscribe_url']}>")
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["List-Unsubscribe"] = ", ".join(unsub)
    msg.set_content(body)
    return msg


def digest(to, subject, body, cfg):
    h = hashlib.sha256("\x1f".join((to.lower(), subject, body, cfg["mail"]["from_email"].lower(),
                                     (cfg["sender"].get("reply_email") or "").lower())).encode("utf-8"))
    return h.hexdigest()[:16]


# ---- ledger, caps, window, health ---------------------------------------------
def ledger_path(root):
    return os.path.join(root, "_mail", "ledger.csv")


def read_ledger(root):
    return campaign._read_csv(ledger_path(root))[0]


def append_ledger(root, row):
    path = ledger_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def timezone(cfg, spec):
    return ZoneInfo(cfg["mail"].get("timezone") or spec.get("operator", {}).get("timezone") or "America/New_York")


def cap_today(root, cfg, today):
    """-> (cap, sent today). Warm-up: a new sending address starts low (mail.warmup = [[days, cap], ...]) before mail.daily_cap."""
    frm = cfg["mail"]["from_email"].strip().lower()
    mine = [r for r in read_ledger(root) if r["From"].lower() == frm and r["Status"] == SENT]
    first = min((dt.date.fromisoformat(r["Date"]) for r in mine), default=today)
    age, cap = (today - first).days, int(cfg["mail"]["daily_cap"])
    for days, c in sorted(cfg["mail"].get("warmup") or []):
        if age < days:
            cap = min(cap, int(c))
            break
    return cap, sum(1 for r in mine if r["Date"] == today.isoformat())


def _hm(text):
    h, m = text.split(":")
    return dt.time(int(h), int(m))


def window(spec, now):
    """-> (open now?, next opening as an aware datetime, today's closing). now is aware, in the recipients' time zone."""
    w = spec["outreach"].get("send_window") or {}
    days = {campaign.DAYS.index(d) for d in (w.get("days") or campaign.DAYS[:5])}
    start, end = _hm(w.get("start", "09:30")), _hm(w.get("end", "11:30"))
    close = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if now.weekday() in days and start <= now.time() < end:
        return True, now, close
    day = now.date() if (now.weekday() in days and now.time() < start) else now.date() + dt.timedelta(days=1)
    while day.weekday() not in days:
        day += dt.timedelta(days=1)
    nxt = dt.datetime.combine(day, start, tzinfo=now.tzinfo)
    return False, nxt, close


def health(name, root, cfg, today):
    """Recent bounce rate from the campaign's events. Too many bounces means the list needs verifying before more mail goes out."""
    rows = campaign._read_csv(os.path.join(campaign.folder(name, root), "events.csv"))[0]
    since = (today - dt.timedelta(days=30)).isoformat()
    sent = sum(1 for r in rows if r["Event"] == "Email sent" and r["Date"] >= since)
    bounced = sum(1 for r in rows if r["Event"] == "Bounced" and r["Date"] >= since)
    limit = float(cfg["mail"].get("bounce_limit", 0.05))
    if sent >= 20 and bounced / sent > limit:
        return f"{bounced} of {sent} emails bounced in the last 30 days (over {limit:.0%}): verify the list before sending more"
    return ""


def record_event(name, root, lead_key, company, to, event, notes="", day=None):
    """Write one engagement event straight to events.csv (sends and bounces); a bounce also suppresses the address."""
    from . import events
    path = os.path.join(campaign.folder(name, root), events.EVENTS_FILE)
    rows, _ = campaign._read_csv(path)
    rows.append({"Date": (day or dt.date.today()).isoformat(), "Lead Key": lead_key, "Company": company, "Email": to.lower(),
                 "Event": event, "Points": events.EVENTS[event], "Notes": notes[:300], "Imported": (day or dt.date.today()).isoformat()})
    campaign._write_csv(path, rows, events.FIELDS)
    if event == events.BOUNCE:
        events._suppress(name, root, [to.lower()])


# ---- providers -------------------------------------------------------------------
class FileProvider:
    """The dry run: writes each message to an outbox folder. Nothing leaves the computer."""
    name = "file"

    def __init__(self, outbox, account=""):
        self.outbox, self._account = outbox, account
        os.makedirs(outbox, exist_ok=True)

    def account(self):
        return self._account

    def send(self, msg):
        n = len([f for f in os.listdir(self.outbox) if f.endswith(".eml")]) + 1
        path = os.path.join(self.outbox, f"{n:04d}-{re.sub(r'[^a-z0-9]+', '-', msg['To'].lower())}.eml")
        with open(path, "wb") as fh:
            fh.write(bytes(msg))
        return os.path.basename(path)

    def close(self):
        pass


def smtp_settings():
    """Environment first (LEADENGINE_SMTP_HOST, _PORT, _USER, _PASSWORD, _SECURITY), then ~/.config/leadengine/smtp.json."""
    path = os.path.join(config_dir(), "smtp.json")
    f = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            f = json.load(fh)
    env = lambda k: os.environ.get("LEADENGINE_SMTP_" + k.upper())
    s = {k: env(k) or f.get(k) for k in ("host", "port", "user", "password", "security")}
    missing = [k for k in ("host", "user", "password") if not s[k]]
    if missing:
        raise SetupError("SMTP is not set up (missing " + ", ".join(missing) + "). Set LEADENGINE_SMTP_HOST, LEADENGINE_SMTP_USER and "
                         f"LEADENGINE_SMTP_PASSWORD, or write them to {path}. See docs/EMAIL_SENDING.md. Nothing was sent.")
    s["security"] = (s["security"] or ("ssl" if str(s["port"]) == "465" else "starttls")).lower()
    s["port"] = int(s["port"] or (465 if s["security"] == "ssl" else 587))
    return s


class SMTPProvider:
    name = "smtp"

    def __init__(self, settings=None, smtp=smtplib.SMTP, smtp_ssl=smtplib.SMTP_SSL):
        self.s = settings or smtp_settings()
        self._smtp, self._smtp_ssl, self.conn = smtp, smtp_ssl, None

    def account(self):
        return self.s["user"]

    def _connect(self):
        ctx = ssl.create_default_context()
        try:
            if self.s["security"] == "ssl":
                c = self._smtp_ssl(self.s["host"], self.s["port"], timeout=30, context=ctx)
            else:
                c = self._smtp(self.s["host"], self.s["port"], timeout=30)
                c.ehlo()
                c.starttls(context=ctx)
                c.ehlo()
            c.login(self.s["user"], self.s["password"])
        except smtplib.SMTPAuthenticationError as exc:
            raise Fatal(f"SMTP login refused ({exc.smtp_code}): check the user and app password") from exc
        except (OSError, smtplib.SMTPException) as exc:
            raise Fatal(f"could not connect to {self.s['host']}:{self.s['port']}: {exc}") from exc
        self.conn = c

    def send(self, msg):
        if self.conn is None:
            self._connect()
        try:
            refused = self.conn.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            raise Permanent(_smtp_reason(exc.recipients)) from exc
        except smtplib.SMTPSenderRefused as exc:
            raise Fatal(f"the server will not send as {msg['From']} ({exc.smtp_code})") from exc
        except smtplib.SMTPDataError as exc:
            if 500 <= exc.smtp_code < 600:
                raise Permanent(f"{exc.smtp_code} {exc.smtp_error!r}") from exc
            raise Temporary(f"{exc.smtp_code} {exc.smtp_error!r}") from exc
        except smtplib.SMTPServerDisconnected as exc:
            self.conn = None
            raise Temporary("server disconnected") from exc
        except (OSError, smtplib.SMTPException) as exc:
            raise Temporary(str(exc)) from exc
        if refused:
            raise Permanent(_smtp_reason(refused))
        return msg["Message-ID"]

    def close(self):
        if self.conn is not None:
            try:
                self.conn.quit()
            except (OSError, smtplib.SMTPException):
                pass
            self.conn = None


def _smtp_reason(recipients):
    return "; ".join(f"{a}: {c} {m.decode(errors='replace') if isinstance(m, bytes) else m}" for a, (c, m) in recipients.items())


GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"


class GmailProvider:
    """The Gmail API with your own OAuth client (Google Cloud > Desktop app). Tokens stay in ~/.config/leadengine/."""
    name = "gmail"
    API = "https://gmail.googleapis.com/gmail/v1/users/me"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self, cdir=None, opener=None):
        self.cdir = cdir or config_dir()
        self.open = opener or urllib.request.urlopen
        self.client = _gmail_client(self.cdir)
        tpath = os.path.join(self.cdir, "gmail-token.json")
        if not os.path.exists(tpath):
            raise SetupError("Gmail is not authorised on this computer. Run: python3 -m leadengine mail auth gmail (see docs/EMAIL_SENDING.md). Nothing was sent.")
        with open(tpath, encoding="utf-8") as fh:
            self.token = json.load(fh)
        self.access = None

    def _refresh(self):
        body = urllib.parse.urlencode({"client_id": self.client["client_id"], "client_secret": self.client.get("client_secret", ""),
                                       "refresh_token": self.token["refresh_token"], "grant_type": "refresh_token"}).encode()
        try:
            with self.open(urllib.request.Request(self.TOKEN_URL, data=body), timeout=30) as r:
                self.access = json.load(r)["access_token"]
        except urllib.error.HTTPError as exc:
            raise Fatal("Gmail refused the saved authorisation (expired or revoked): run leadengine mail auth gmail again") from exc
        except OSError as exc:
            raise Temporary(f"could not reach Google: {exc}") from exc

    def _call(self, method, path, payload=None, retry=True):
        if self.access is None:
            self._refresh()
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.API + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + self.access, "Content-Type": "application/json"})
        try:
            with self.open(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode(errors="replace") if hasattr(exc, "read") else ""
            if exc.code == 401 and retry:
                self._refresh()
                return self._call(method, path, payload, retry=False)
            if exc.code in (403, 429) and re.search(r"limit|quota|rate", text, re.I):
                raise Fatal("Gmail's sending limit is reached for now; stop for today") from exc
            if exc.code in (401, 403):
                raise Fatal(f"Gmail refused the request ({exc.code}): check the authorisation and the From address") from exc
            if exc.code == 400:
                raise Permanent(f"Gmail rejected the message (400): {text[:200]}") from exc
            raise Temporary(f"Gmail error {exc.code}") from exc
        except OSError as exc:
            raise Temporary(f"could not reach Gmail: {exc}") from exc

    def account(self):
        return self._call("GET", "/profile")["emailAddress"]

    def send(self, msg):
        raw = base64.urlsafe_b64encode(bytes(msg)).decode("ascii")
        return self._call("POST", "/messages/send", {"raw": raw})["id"]

    def search(self, query, limit=200):
        """-> [{"from", "subject", "date", "snippet", "failed"}] for messages matching a Gmail search (needs the read permission)."""
        out, page = [], None
        while len(out) < limit:
            q = {"q": query, "maxResults": min(100, limit - len(out))}
            if page:
                q["pageToken"] = page
            res = self._call("GET", "/messages?" + urllib.parse.urlencode(q))
            for m in res.get("messages", []):
                full = self._call("GET", f"/messages/{m['id']}?format=metadata&metadataHeaders=From&metadataHeaders=Subject"
                                         "&metadataHeaders=Date&metadataHeaders=X-Failed-Recipients")
                h = {x["name"].lower(): x["value"] for x in full.get("payload", {}).get("headers", [])}
                out.append({"from": email.utils.parseaddr(h.get("from", ""))[1].lower(), "subject": h.get("subject", ""),
                            "date": h.get("date", ""), "snippet": full.get("snippet", ""), "failed": h.get("x-failed-recipients", "")})
            page = res.get("nextPageToken")
            if not page:
                break
        return out

    def close(self):
        pass


def _gmail_client(cdir):
    path = os.path.join(cdir, "gmail-client.json")
    if not os.path.exists(path):
        raise SetupError(f"No Gmail OAuth client at {path}. Download it from Google Cloud (Credentials > OAuth client ID > Desktop app) "
                         "and save it there. See docs/EMAIL_SENDING.md. Nothing was sent.")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("installed") or data.get("web") or data


def authorize_gmail(read=False, cdir=None, opener=None, browser=None, timeout=300):
    """One-time sign-in on your own computer: opens Google's consent page, catches the answer on 127.0.0.1, saves the refresh token."""
    import http.server
    import webbrowser
    cdir = cdir or config_dir()
    client = _gmail_client(cdir)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state, got = secrets.token_urlsafe(16), {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            if q.get("state") == state:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and go back to the terminal.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    srv.timeout = timeout
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    scopes = [GMAIL_SEND] + ([GMAIL_READ] if read else [])
    url = client.get("auth_uri", "https://accounts.google.com/o/oauth2/auth") + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": " ".join(scopes),
        "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent", "state": state})
    print("Opening Google's consent page. If it does not open, paste this into your browser:\n" + url)
    (browser or webbrowser.open)(url)
    srv.handle_request()
    srv.server_close()
    if "code" not in got:
        raise SystemExit("No answer from Google (" + got.get("error", "timed out") + "). Nothing was saved.")
    body = urllib.parse.urlencode({"code": got["code"], "client_id": client["client_id"], "client_secret": client.get("client_secret", ""),
                                   "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier}).encode()
    with (opener or urllib.request.urlopen)(urllib.request.Request(client.get("token_uri", GmailProvider.TOKEN_URL), data=body), timeout=30) as r:
        tok = json.load(r)
    if "refresh_token" not in tok:
        raise SystemExit("Google did not return a refresh token; remove the app's access in your Google account and run this again.")
    path = os.path.join(cdir, "gmail-token.json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"refresh_token": tok["refresh_token"], "scope": tok.get("scope", " ".join(scopes))}, fh)
    return path


PROVIDERS = {"smtp": lambda **kw: SMTPProvider(), "gmail": lambda **kw: GmailProvider(), "file": lambda outbox, account="", **kw: FileProvider(outbox, account)}


def register(name, factory):
    """Add a provider, e.g. register("ses", lambda **kw: SESProvider()). It needs account() -> sending address and send(msg) -> id."""
    PROVIDERS[name] = factory


def provider(name, outbox, cfg):
    if name not in PROVIDERS:
        raise SetupError(f"Unknown mail provider {name!r}; choose one of {', '.join(sorted(PROVIDERS))}")
    return PROVIDERS[name](outbox=outbox, account=cfg["mail"]["from_email"])


def check_account(prov, cfg):
    """The From address must be the account that sends (Gmail checks this itself; SMTP relays may use a non-email login)."""
    acct = (prov.account() or "").strip().lower()
    frm = cfg["mail"]["from_email"].strip().lower()
    if prov.name == "gmail" and acct != frm:
        raise SetupError(f"Gmail is signed in as {acct} but mail.from_email is {frm}; they must match. Nothing was sent.")
    if prov.name == "smtp" and "@" in acct and acct != frm:
        return f"SMTP login {acct} differs from mail.from_email {frm}; the server must be allowed to send as {frm}"
    return ""


# ---- the send loop ----------------------------------------------------------------
def send_all(items, prov, *, name, root, cfg, spec, mailing="", batch="", recheck=None, on_sent=None, clock=None, sleep=time.sleep,
             wait=False, rng=None, out=print):
    """items: [{"to", "lead_key", "company", "subject", "body"}] in send order. recheck(item) -> reason to skip now, or "".
    Sends one at a time with a random pause, inside the send window and the day's cap; stops on a fatal error or too many failures.
    -> {"sent", "skipped", "failed", "bounced", "stopped"}"""
    tz = timezone(cfg, spec)
    clock = clock or (lambda: dt.datetime.now(tz))
    rng = rng or random.Random()
    lo, hi = cfg["mail"].get("delay_seconds") or [60, 180]
    res = {"sent": 0, "skipped": 0, "failed": 0, "bounced": 0, "stopped": ""}
    frm = cfg["mail"]["from_email"].strip()
    dry = prov.name == "file"                  # the dry run: no window, no pauses, nothing counted as sent; the cap still applies

    def log(item, status, mid="", err=""):
        now = clock()
        append_ledger(root, {"Time": now.isoformat(timespec="seconds"), "Date": now.date().isoformat(), "From": frm, "To": item["to"],
                             "Campaign": name, "Mailing": mailing, "Batch": batch, "Lead Key": item.get("lead_key", ""),
                             "Company": item.get("company", ""), "Subject": item["subject"], "Status": status, "Provider": prov.name,
                             "Message ID": mid, "Error": err[:300]})

    try:
        first = True
        for item in items:
            now = clock()
            is_open, nxt, _ = window(spec, now)
            if dry:
                pass
            elif not is_open:
                if not wait:
                    res["stopped"] = f"outside the send window; it next opens {nxt:%a %Y-%m-%d %H:%M %Z}"
                    break
                out(f"Waiting for the send window to open at {nxt:%a %H:%M %Z} ...")
                sleep(max(0.0, (nxt - now).total_seconds()))
                now = clock()
                first = True
            elif not first:
                pause = rng.uniform(float(lo), float(hi))
                sleep(pause)
                now = clock()
                if not window(spec, now)[0]:
                    res["stopped"] = "the send window closed; the rest go in the next window"
                    break
            cap, used = cap_today(root, cfg, now.date())
            if used + (res["sent"] if dry else 0) >= cap:
                res["stopped"] = f"today's cap of {cap} is used (warm-up limits a new address); the rest go tomorrow"
                break
            bad = health(name, root, cfg, now.date())
            if bad:
                res["stopped"] = bad
                break
            why = recheck(item) if recheck else ""
            if why:
                log(item, "skipped", err=why)
                res["skipped"] += 1
                continue
            first = False
            msg = build(cfg, item["to"], item["subject"], item["body"])
            try:
                mid = prov.send(msg)
            except Permanent as exc:
                log(item, "bounced", err=str(exc))
                record_event(name, root, item.get("lead_key", ""), item.get("company", ""), item["to"], "Bounced", str(exc), now.date())
                res["bounced"] += 1
                res["failed"] += 1
            except Temporary as exc:
                log(item, "failed", err=str(exc))
                res["failed"] += 1
            except Fatal as exc:
                log(item, "failed", err=str(exc))
                res["failed"] += 1
                res["stopped"] = str(exc)
                break
            else:
                log(item, "dry-run" if dry else SENT, mid)
                if not dry:
                    record_event(name, root, item.get("lead_key", ""), item.get("company", ""), item["to"], "Email sent",
                                 f"{mailing or 'sequence'} {batch}".strip(), now.date())
                    if on_sent:
                        on_sent(item, mid, now)
                res["sent"] += 1
            if res["failed"] >= int(cfg["mail"].get("max_failures", 3)):
                res["stopped"] = f"{res['failed']} failures in this batch; check the list and the account before sending more"
                break
    finally:
        prov.close()
    return res
