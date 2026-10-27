"""Read replies, opt-outs and bounces back from the sending mailbox, so nobody who answered gets another marketing email.

  leadengine campaign mail sync <name> [--provider gmail|imap] [--since YYYY-MM-DD]

Looks only for mail FROM the addresses this campaign sent to (and bounce notices from mailer daemons), since the first send.
Each hit becomes an event and goes through the same import as a hand-made Events CSV:
  a reply is "Replied" (or an opt-out when it says "no thanks", "unsubscribe", "remove me" ...); a bounce is "Bounced".
Opt-outs and bounces go to suppress.csv; any reply stops the lead's planned tasks and future mailings.
It reads headers and the short preview only, and never replies, deletes or marks anything.

gmail: the Gmail API, authorised with read access (leadengine mail auth gmail --read).
imap:  any IMAP mailbox (LEADENGINE_IMAP_HOST, _USER, _PASSWORD; user and password default to the SMTP ones)."""
import datetime as dt
import email
import email.utils
import imaplib
import json
import os
import re

from . import campaign, events, mailer

DAEMON = re.compile(r"mailer-daemon|postmaster|mail delivery", re.I)
AUTO = re.compile(r"automatic reply|auto-?reply|autoreply|out of (the )?office|away from (the )?office|on vacation", re.I)
ADDR = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")


def imap_settings():
    path = os.path.join(mailer.config_dir(), "imap.json")
    f = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            f = json.load(fh)
    env = os.environ.get
    s = {"host": env("LEADENGINE_IMAP_HOST") or f.get("host"),
         "user": env("LEADENGINE_IMAP_USER") or f.get("user") or env("LEADENGINE_SMTP_USER"),
         "password": env("LEADENGINE_IMAP_PASSWORD") or f.get("password") or env("LEADENGINE_SMTP_PASSWORD"),
         "folder": env("LEADENGINE_IMAP_FOLDER") or f.get("folder") or "INBOX"}
    missing = [k for k in ("host", "user", "password") if not s[k]]
    if missing:
        raise mailer.SetupError("IMAP is not set up (missing " + ", ".join(missing) + "): set LEADENGINE_IMAP_HOST (imap.gmail.com for Gmail) "
                                "and the user and password. See docs/EMAIL_SENDING.md.")
    return s


class IMAPReader:
    def __init__(self, settings=None, imap=imaplib.IMAP4_SSL):
        self.s, self._imap = settings or imap_settings(), imap

    def search(self, senders, since, daemons=True):
        c = self._imap(self.s["host"])
        try:
            c.login(self.s["user"], self.s["password"])
            c.select(self.s["folder"], readonly=True)
            day = since.strftime("%d-%b-%Y")
            ids = []
            for who in sorted(senders):
                ids += c.search(None, "SINCE", day, "FROM", f'"{who}"')[1][0].split()
            if daemons:
                for who in ("mailer-daemon", "postmaster"):
                    ids += c.search(None, "SINCE", day, "FROM", who)[1][0].split()
            out = []
            for i in dict.fromkeys(ids):
                raw = c.fetch(i, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.2000>)")[1]
                parts = [p[1] for p in raw if isinstance(p, tuple)]
                msg = email.message_from_bytes(parts[0] if parts else b"")
                text = (parts[1] if len(parts) > 1 else b"").decode("utf-8", "replace")
                out.append({"from": email.utils.parseaddr(msg.get("From", ""))[1].lower(), "subject": msg.get("Subject", ""),
                            "date": msg.get("Date", ""), "snippet": re.sub(r"\s+", " ", text)[:500], "failed": msg.get("X-Failed-Recipients", "")})
            return out
        finally:
            try:
                c.logout()
            except (OSError, imaplib.IMAP4.error):
                pass


def _gmail_query(senders, since):
    return [f"from:({' OR '.join(chunk)}) after:{since:%Y/%m/%d}" for chunk in
            (sorted(senders)[i:i + 20] for i in range(0, len(senders), 20))] + [f"from:(mailer-daemon OR postmaster) after:{since:%Y/%m/%d}"]


def _day(text, fallback):
    try:
        return email.utils.parsedate_to_datetime(text).date()
    except (TypeError, ValueError, IndexError):
        return fallback


def to_events(found, sent_to, today):
    """Mailbox hits -> event rows (Date, Event, Email, Notes). A bounce names the original recipient; a reply comes from them."""
    rows = []
    for m in found:
        day = _day(m["date"], today)
        if DAEMON.search(m["from"]) or DAEMON.search(m["subject"]):
            hits = {a.lower() for a in ADDR.findall(m.get("failed", "") + " " + m.get("snippet", ""))} & sent_to
            rows += [{"Date": day.isoformat(), "Event": "Bounced", "Email": a, "Notes": m["subject"][:200]} for a in sorted(hits)]
        elif m["from"] in sent_to and not AUTO.search(m["subject"]):
            rows.append({"Date": day.isoformat(), "Event": "Replied", "Email": m["from"], "Notes": f"{m['subject']} | {m['snippet']}"[:300]})
    return rows


def sync(name, root=campaign.ROOT, provider_name="gmail", since=None, reader=None, today=None):
    campaign.load(name, root)
    today = today or dt.date.today()
    mine = [r for r in mailer.read_ledger(root) if r["Campaign"] == name and r["Status"] == mailer.SENT]
    if not mine:
        return {"found": 0, "events": 0, "import": None}
    sent_to = {r["To"].lower() for r in mine}
    since = since or min(dt.date.fromisoformat(r["Date"]) for r in mine)
    if reader is None:
        reader = mailer.GmailProvider() if provider_name == "gmail" else IMAPReader()
    if isinstance(reader, mailer.GmailProvider):
        found = []
        for q in _gmail_query(sent_to, since):
            found += reader.search(q)
    else:
        found = reader.search(sent_to, since)
    rows = to_events(found, sent_to, today)
    if not rows:
        return {"found": len(found), "events": 0, "import": None}
    path = os.path.join(campaign.folder(name, root), "mail", f"sync-{today.isoformat()}.csv")
    campaign._write_csv(path, rows, ["Date", "Event", "Email", "Notes"])
    res = events.import_events(name, path, root, today)
    campaign.log(name, "mail_sync", root, provider=provider_name, found=len(found), events=len(rows))
    return {"found": len(found), "events": len(rows), "import": res}
