"""Engagement feedback for a campaign: replies, opt-outs, bounces, clicks and bookings flow back into it.

  leadengine campaign events import <name> FILE.csv     log events; opt-outs and bounces go to suppress.csv; replies stop the sequence
  leadengine campaign events report <name> [--json]     interest level per lead, and reply / booking / opt-out rates by source and signal

FILE.csv is the workbook's Events tab exported as CSV, the tracker's export, or any sheet you keep by hand. Columns (case-insensitive):
  Date, Event, and one of Lead Key / Email / Company to say who; optional Notes (a reply's text, used to spot "no thanks").
Event names and points are the workbook's Config tab rows 96-106 (EVENTS below), so interest levels match the sheet.

Nothing here contacts anyone. It only changes files inside campaigns/<name>/."""
import datetime as dt
import os
import re

from . import campaign
from .filters import norm_name

# Same names and points as the workbook's Config tab (tools/build_template.py EVENTS). "Bounced" is engine-only and scores nothing.
EVENTS = {
    "Email sent": 0, "Email opened": 1, "Email link clicked": 5, "Website visit": 5, "Key page visit (portfolio / pricing / contact)": 10,
    "Form submitted": 25, "Replied": 20, "Positive reply": 30, "Call booked": 40, "Proposal viewed": 30, "Unsubscribed / Not interested": -100,
    "Bounced": 0,
}
OPT_OUT, BOUNCE = "Unsubscribed / Not interested", "Bounced"
STOPS = {"Replied", "Positive reply", "Call booked", "Form submitted", OPT_OUT, BOUNCE}     # a person answered, or cannot be reached
ALIASES = {
    "sent": "Email sent", "open": "Email opened", "opened": "Email opened", "click": "Email link clicked", "clicked": "Email link clicked",
    "visit": "Website visit", "key page": "Key page visit (portfolio / pricing / contact)", "form": "Form submitted",
    "reply": "Replied", "replied": "Replied", "positive": "Positive reply", "interested": "Positive reply", "booked": "Call booked",
    "meeting booked": "Call booked", "proposal": "Proposal viewed", "opt out": OPT_OUT, "opt-out": OPT_OUT, "optout": OPT_OUT,
    "unsubscribe": OPT_OUT, "unsubscribed": OPT_OUT, "not interested": OPT_OUT, "no thanks": OPT_OUT, "do not contact": OPT_OUT,
    "bounce": BOUNCE, "bounced": BOUNCE, "undeliverable": BOUNCE,
}
OPT_OUT_TEXT = re.compile(r"\b(no,? thanks|no thank you|unsubscribe|remove me|take me off|stop (emailing|contacting)|not interested|"
                          r"do not (contact|email)|don'?t (contact|email))\b", re.I)
WINDOW_DAYS, HOT, WARM = 30, 40, 15          # Config rows 92-94
EVENTS_FILE, SUPPRESS_FILE = "events.csv", "suppress.csv"
FIELDS = ["Date", "Lead Key", "Company", "Email", "Event", "Points", "Notes", "Imported"]


def canonical(name, notes=""):
    """Map an event name (sheet name or a common alias) to the sheet's name. A reply whose text says 'no thanks' is an opt-out."""
    raw = (name or "").strip()
    ev = next((k for k in EVENTS if k.lower() == raw.lower()), None) or ALIASES.get(raw.lower())
    if ev is None:
        return None
    if ev in ("Replied", "Positive reply") and OPT_OUT_TEXT.search(notes or ""):
        return OPT_OUT
    return ev


def _get(row, *names):
    low = {k.strip().lower().replace("_", " "): v for k, v in row.items() if k}
    return next(((low.get(n) or "").strip() for n in names if (low.get(n) or "").strip()), "")


def _date(text):
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _leads(name, root):
    """Every lead the campaign has delivered, keyed for matching: lead key, email, normalised company."""
    d = campaign.folder(name, root)
    rows = []
    for f in ("approved.csv", "pending.csv", "rejected.csv"):
        rows += campaign._read_csv(os.path.join(d, f))[0]
    by_key, by_email, by_company = {}, {}, {}
    for r in rows:
        by_key.setdefault(r.get("Lead Key", ""), r)
        if (r.get("Email") or "").strip():
            by_email.setdefault(r["Email"].strip().lower(), r)
        by_company.setdefault(norm_name(r.get("Company", "")), r)
    return by_key, by_email, by_company


def _match(row, idx):
    by_key, by_email, by_company = idx
    key, email, company = _get(row, "lead key", "dedupe key", "key"), _get(row, "email", "from").lower(), _get(row, "company")
    if key and key in by_key:
        return by_key[key]
    if email and email in by_email:
        return by_email[email]
    if company and norm_name(company) in by_company:
        return by_company[norm_name(company)]
    return None


def _suppress(name, root, values):
    path = os.path.join(campaign.folder(name, root), SUPPRESS_FILE)
    rows, _ = campaign._read_csv(path)
    have = {r["value"].strip().lower() for r in rows if r.get("value")}
    added = [v for v in dict.fromkeys(values) if v and v.strip().lower() not in have]
    if added:
        campaign._write_csv(path, rows + [{"value": v} for v in added], ["value"])
    return added


def _stop_tasks(name, root, stops):
    """stops: {lead key: (date, event)}. Open tasks for that lead dated on or after the event are marked Stopped, so they are not sent."""
    odir = os.path.join(campaign.folder(name, root), "outreach")
    n = 0
    for f in sorted(os.listdir(odir)) if os.path.isdir(odir) else []:
        if not f.startswith("tasks-"):
            continue
        path = os.path.join(odir, f)
        rows, fields = campaign._read_csv(path)
        changed = False
        for t in rows:
            hit = stops.get(t.get("Lead Key", ""))
            if not hit or (t.get("Done (Y/N)") or "").strip().upper() in ("Y", "STOPPED"):
                continue
            day = _date(t.get("Date"))
            if day and day >= hit[0]:
                t["Done (Y/N)"] = "Stopped"
                t["Approved to send (Y/N)"] = ""
                t["Outcome / notes"] = f"stopped: {hit[1]} on {hit[0]}" + (f"; {t['Outcome / notes']}" if t.get("Outcome / notes") else "")
                changed, n = True, n + 1
        if changed:
            campaign._write_csv(path, rows, fields)
    return n


def import_events(name, path, root=campaign.ROOT, today=None):
    """-> summary dict. Re-importing the same file adds nothing (rows are de-duplicated on date, lead and event)."""
    campaign.load(name, root)
    rows, _ = campaign._read_csv(path)
    if not rows:
        raise SystemExit(f"{path} has no rows")
    idx = _leads(name, root)
    epath = os.path.join(campaign.folder(name, root), EVENTS_FILE)
    old, _ = campaign._read_csv(epath)
    seen = {(r["Date"], r["Lead Key"] or r["Email"] or norm_name(r["Company"]), r["Event"]) for r in old}
    new, unknown_event, unmatched, sup, stops = [], [], [], [], {}
    stamp = (today or dt.date.today()).isoformat()
    for i, r in enumerate(rows, 2):
        notes = _get(r, "notes", "text", "snippet", "outcome")
        ev = canonical(_get(r, "event", "type"), notes)
        day = _date(_get(r, "date", "timestamp"))
        if ev is None or day is None:
            unknown_event.append(f"row {i}: " + ("unknown event " + repr(_get(r, "event", "type")) if ev is None else "no readable date"))
            continue
        lead = _match(r, idx)
        key = lead["Lead Key"] if lead else _get(r, "lead key", "dedupe key", "key")
        company = lead["Company"] if lead else _get(r, "company")
        email = (_get(r, "email", "from") or (lead or {}).get("Email", "")).lower()
        if not (key or email or company):
            unmatched.append(f"row {i}: no lead key, email or company")
            continue
        if not lead:
            unmatched.append(f"row {i}: {key or email or company} is not a lead in this campaign (logged anyway)")
        sig = (day.isoformat(), key or email or norm_name(company), ev)
        if sig in seen:
            continue
        seen.add(sig)
        new.append({"Date": day.isoformat(), "Lead Key": key, "Company": company, "Email": email, "Event": ev, "Points": EVENTS[ev],
                    "Notes": notes[:300], "Imported": stamp})
        if ev in (OPT_OUT, BOUNCE):                     # the address (or, with none, the company) is never planned again
            sup.append(email or company)
            if ev == OPT_OUT and key:
                sup.append(key)
        if ev in STOPS and key and (key not in stops or day < stops[key][0]):
            stops[key] = (day, ev)
    campaign._write_csv(epath, old + new, FIELDS)
    added = _suppress(name, root, [v for v in sup if v])
    stopped = _stop_tasks(name, root, stops)
    counts = {}
    for e in new:
        counts[e["Event"]] = counts.get(e["Event"], 0) + 1
    summary = {"imported": len(new), "by_event": counts, "suppressed_added": added, "tasks_stopped": stopped,
               "unmatched": unmatched, "skipped": unknown_event}
    campaign.log(name, "events_import", root, file=os.path.basename(path), imported=len(new), suppressed=len(added), stopped=stopped)
    return summary


def interest(events, today, window=WINDOW_DAYS):
    """Interest level for one lead's events, as the Leads tab computes it: Opted out / Hot / Warm / Cold / No contact yet."""
    if not events:
        return "No contact yet"
    if any(e["Event"] == OPT_OUT for e in events):
        return "Opted out"
    pts = sum(int(e["Points"]) for e in events if (_date(e["Date"]) or dt.date.min) >= today - dt.timedelta(days=window))
    return "Hot" if pts >= HOT else "Warm" if pts >= WARM else "Cold"


def _contacted(name, root):
    """Lead keys whose first email is marked Done = Y in a task file, with the date."""
    odir = os.path.join(campaign.folder(name, root), "outreach")
    out = {}
    for f in sorted(os.listdir(odir)) if os.path.isdir(odir) else []:
        if f.startswith("tasks-"):
            for t in campaign._read_csv(os.path.join(odir, f))[0]:
                if t.get("Step") == "1" and (t.get("Done (Y/N)") or "").strip().upper() == "Y":
                    out.setdefault(t["Lead Key"], t["Date"])
    return out


def report(name, root=campaign.ROOT, today=None, min_contacts=200):
    """Interest per lead, and outcome rates by Source and Primary Signal. Rates are shown with their counts; below min_contacts
    contacted leads the report says the sample is too small to tune scoring weights from."""
    today = today or dt.date.today()
    d = campaign.folder(name, root)
    approved, _ = campaign._read_csv(os.path.join(d, "approved.csv"))
    evs, _ = campaign._read_csv(os.path.join(d, EVENTS_FILE))
    by_lead = {}
    for e in evs:
        by_lead.setdefault(e["Lead Key"], []).append(e)
    sent = _contacted(name, root)
    for e in evs:                                        # a logged "Email sent" also counts as contacted
        if e["Event"] == "Email sent" and e["Lead Key"]:
            sent.setdefault(e["Lead Key"], e["Date"])
    levels = {}
    for r in approved:
        levels[r["Lead Key"]] = interest(by_lead.get(r["Lead Key"], []), today)

    def bucket(field):
        out = {}
        for r in approved:
            k = r.get(field) or "(blank)"
            b = out.setdefault(k, {"approved": 0, "contacted": 0, "replied": 0, "booked": 0, "opted_out": 0, "bounced": 0})
            b["approved"] += 1
            names = {e["Event"] for e in by_lead.get(r["Lead Key"], [])}
            if r["Lead Key"] in sent or names - {"Email opened", "Email link clicked", "Website visit"}:
                b["contacted"] += 1
            b["replied"] += bool(names & {"Replied", "Positive reply", "Call booked", OPT_OUT})
            b["booked"] += "Call booked" in names
            b["opted_out"] += OPT_OUT in names
            b["bounced"] += BOUNCE in names
        for b in out.values():
            c = b["contacted"]
            b["reply_rate"] = round(b["replied"] / c, 3) if c else None
            b["booking_rate"] = round(b["booked"] / c, 3) if c else None
        return out

    contacted = sum(1 for r in approved if r["Lead Key"] in sent or by_lead.get(r["Lead Key"]))
    tally = {}
    for v in levels.values():
        tally[v] = tally.get(v, 0) + 1
    return {"campaign": name, "events": len(evs), "contacted": contacted, "interest": tally,
            "hot_leads": sorted(r["Company"] for r in approved if levels.get(r["Lead Key"]) == "Hot"),
            "by_source": bucket("Source"), "by_signal": bucket("Primary Signal"),
            "tuning": ("enough contacts to compare signals; change points in config.json only where a signal clearly outperforms"
                       if contacted >= min_contacts else f"{contacted} of {min_contacts} contacts needed before changing scoring weights from these rates")}
