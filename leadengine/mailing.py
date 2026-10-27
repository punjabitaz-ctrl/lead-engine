"""Marketing mailings: one template sent in small, approved batches to a campaign's contacts.

  mail plan    <name> <id> --template FILE [--list FILE]   pick recipients, split them into batches, write batch 1's preview
  mail preview <name> <id> --batch N                       rendered samples, every recipient, the count, flags and a hash
  mail approve <name> <id> --batch N --hash H              a person approves exactly what they read
  mail send    <name> <id> --batch N [--dry-run] [--wait]  sends that batch, paced, inside the send window and the day's cap
  mail test    <name> <id> --to YOUR-OWN-ADDRESS            one rendered sample to your own address
  mail status  <name> [<id>]
  mail sync    <name> [--provider gmail|imap]           replies, opt-outs and bounces back into events.csv and suppress.csv

Recipients come from approved.csv (leads a person kept at the review gate) unless --list names another CSV. Everyone is checked again
right before each email, and left out when they: opted out, replied, booked, bounced, are in suppress.csv, were already sent this
mailing, got any email from this campaign's sender in the last mail.min_days_between days, are still in an active outreach sequence,
have an email status outside mail.allowed_email_status, or share a business domain with someone earlier in the list.

Template file: the first line is "Subject: ...", then a blank line, then the body. Merge fields:
  {first_name} (falls back to "there"), {last_name}, {company}, {city}, {state}, {website}, {title},
  {sender_name}, {business_name}, {portfolio_url}, {booking_link}
A recipient missing a field the template uses (other than first_name) is left out rather than sent a gap.
The compliance footer (name, business, postal address, how to opt out) is added to every email; do not write your own."""
import datetime as dt
import hashlib
import json
import os
import re

from . import campaign, config, mailer
from .contacts import FREE_MAIL

LEAD_FIELDS = {"first_name": "First Name", "last_name": "Last Name", "company": "Company", "city": "City", "state": "State",
               "website": "Website", "title": "Title"}
SENDER_FIELDS = {"sender_name": "name", "business_name": "business", "portfolio_url": "portfolio_url", "booking_link": "booking_link"}
TOKEN = re.compile(r"\{([a-z_]+)\}")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
SAMPLES = 5


def mail_dir(name, mailing, root):
    return os.path.join(campaign.folder(name, root), "mail", mailing)


def load_cfg(name, root):
    return config.load(os.path.join(campaign.folder(name, root), "config.json"))


def read_template(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read().replace("\r\n", "\n")
    first, _, body = text.partition("\n")
    if not first.lower().startswith("subject:"):
        raise SystemExit(f"{path}: the first line must be 'Subject: ...', then a blank line, then the body")
    subject, body = first.split(":", 1)[1].strip(), body.strip("\n")
    unknown = sorted({t for t in TOKEN.findall(subject + body) if t not in LEAD_FIELDS and t not in SENDER_FIELDS})
    if unknown:
        raise SystemExit(f"{path}: unknown merge field(s) {', '.join('{' + u + '}' for u in unknown)}; "
                         f"use {', '.join('{' + k + '}' for k in list(LEAD_FIELDS) + list(SENDER_FIELDS))}")
    if re.search(r"\[[^\]]{2,}\]", subject + body):
        raise SystemExit(f"{path}: still has a [placeholder]; write the real words before planning")
    return subject, body


def render(subject, body, row, cfg):
    """-> (subject, full body with the compliance footer, [missing fields])."""
    vals, missing = {}, []
    for k, col in LEAD_FIELDS.items():
        vals[k] = (row.get(col) or "").strip()
    vals["first_name"] = vals["first_name"].title() if vals["first_name"].isupper() else vals["first_name"]
    for k, key in SENDER_FIELDS.items():
        vals[k] = str(cfg["sender"].get(key) or "").strip()
    used = set(TOKEN.findall(subject + body))
    for k in sorted(used):
        if not vals.get(k) and k not in ("first_name", "booking_link"):
            missing.append(k)
    vals["first_name"] = vals["first_name"] or "there"
    fill = lambda t: TOKEN.sub(lambda m: vals.get(m.group(1), ""), t)
    return fill(subject), fill(body).rstrip() + "\n\n" + mailer.footer(cfg) + "\n", missing


# ---- who may get this mailing ----------------------------------------------------
def context(name, root, cfg, mailing, today):
    """Everything that can rule a recipient out, read fresh from the files."""
    from . import events
    d = campaign.folder(name, root)
    ev = campaign._read_csv(os.path.join(d, events.EVENTS_FILE))[0]
    stops = [r for r in ev if r["Event"] in events.STOPS]
    ledger = mailer.read_ledger(root)
    frm = cfg["mail"]["from_email"].strip().lower()
    last = {}
    for r in ledger:
        if r["Status"] == mailer.SENT and r["From"].lower() == frm:
            last[r["To"].lower()] = max(last.get(r["To"].lower(), ""), r["Date"])
    this = {r["To"].lower() for r in ledger if r["Status"] == mailer.SENT and r["Campaign"] == name and r["Mailing"] == mailing}
    active = set()
    odir = os.path.join(d, "outreach")
    for f in sorted(os.listdir(odir)) if os.path.isdir(odir) else []:
        if f.startswith("tasks-"):
            for t in campaign._read_csv(os.path.join(odir, f))[0]:
                if (t.get("Done (Y/N)") or "").strip().upper() not in ("Y", "STOPPED") and t.get("Date", "") >= today.isoformat():
                    active.add(t.get("Lead Key", ""))
    return {"sup": campaign.load_suppressions(name, root), "stop_keys": {r["Lead Key"] for r in stops if r.get("Lead Key")},
            "stop_emails": {r["Email"].lower() for r in stops if r.get("Email")}, "last": last, "this": this, "active": active,
            "today": today}


def blocked(row, ctx, cfg):
    """-> the reason this person must not get the email now, or ""."""
    m = cfg["mail"]
    to = (row.get("Email") or "").strip().lower()
    key = row.get("Lead Key") or campaign.lead_key(row)
    if not mailer.EMAIL.match(to):
        return "no valid email address"
    if campaign.suppressed({**row, "Email": to}, ctx["sup"]) or key.lower() in ctx["sup"]:
        return "suppressed (opted out, bounced or do-not-contact)"
    if key in ctx["stop_keys"] or to in ctx["stop_emails"]:
        return "replied, booked, opted out or bounced"
    if to in ctx["this"]:
        return "already sent this mailing"
    gap = int(m.get("min_days_between", 30))
    if to in ctx["last"] and (ctx["today"] - dt.date.fromisoformat(ctx["last"][to])).days < gap:
        return f"emailed on {ctx['last'][to]} (less than {gap} days ago)"
    if key in ctx["active"]:
        return "still in an active outreach sequence"
    status = (row.get("Email Status") or "").strip()
    if status.lower() not in {s.lower() for s in m.get("allowed_email_status", [])}:
        return f"email status {status or 'blank'!r} is not in mail.allowed_email_status (verify it first)"
    return ""


def _candidates(name, root, list_path):
    rows = campaign._read_csv(list_path or os.path.join(campaign.folder(name, root), "approved.csv"))[0]
    if not rows:
        raise SystemExit("No contacts: " + (f"{list_path} is empty" if list_path else
                         f"approve leads first (leadengine campaign approve {name} FILE), or pass --list FILE"))
    for r in rows:
        r["Lead Key"] = r.get("Lead Key") or campaign.lead_key(r)
    return rows


def _meta_path(name, mailing, root):
    return os.path.join(mail_dir(name, mailing, root), "mailing.json")


def load_mailing(name, mailing, root):
    path = _meta_path(name, mailing, root)
    if not os.path.exists(path):
        raise SystemExit(f"No mailing {mailing!r} in {name}. Plan it: leadengine campaign mail plan {name} {mailing} --template FILE")
    return campaign._read_json(path)


def plan(name, mailing, template_path, root=campaign.ROOT, list_path=None, today=None):
    """Checks the sender and template, picks recipients, splits them into batches. Sends nothing."""
    if not ID.match(mailing):
        raise SystemExit("Mailing id: lower-case letters, digits and hyphens, e.g. nov-intro")
    spec = campaign.load(name, root)
    cfg = load_cfg(name, root)
    today = today or dt.date.today()
    probs = mailer.sender_problems(cfg)
    subject, body = read_template(template_path)
    probs += mailer.subject_problems(subject)
    if probs:
        raise SystemExit("Fix before planning a mailing:\n  - " + "\n  - ".join(probs))
    d = mail_dir(name, mailing, root)
    if os.path.exists(_meta_path(name, mailing, root)):
        raise SystemExit(f"Mailing {mailing!r} already exists; pick a new id (the old one keeps its send history)")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "template.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Subject: {subject}\n\n{body}\n")
    ctx = context(name, root, cfg, mailing, today)
    keep, out, seen, domains = [], [], set(), set()
    for r in _candidates(name, root, list_path):
        to = (r.get("Email") or "").strip().lower()
        why = blocked(r, ctx, cfg)
        dom = to.split("@")[-1] if "@" in to else ""
        if not why and to in seen:
            why = "same address appears earlier in the list"
        if not why and cfg["mail"].get("one_per_domain", True) and dom and dom not in FREE_MAIL and dom in domains:
            why = f"someone at {dom} is already in this mailing"
        s, b, missing = render(subject, body, r, cfg)
        if not why and missing:
            why = "missing " + ", ".join(missing) + " for the template"
        row = {"Lead Key": r["Lead Key"], "Company": r.get("Company", ""), "First Name": r.get("First Name", ""),
               "Last Name": r.get("Last Name", ""), "City": r.get("City", ""), "State": r.get("State", ""), "Website": r.get("Website", ""),
               "Title": r.get("Title", ""), "Email": to, "Email Status": r.get("Email Status", "")}
        if why:
            out.append({**row, "Reason": why})
            continue
        seen.add(to)
        domains.add(dom)
        keep.append(row)
    size = max(1, min(int(cfg["mail"]["batch_size"]), int(cfg["mail"]["daily_cap"])))
    for i, r in enumerate(keep):
        r["Batch"] = i // size + 1
    fields = ["Batch", "Lead Key", "Company", "First Name", "Last Name", "City", "State", "Website", "Title", "Email", "Email Status"]
    campaign._write_csv(os.path.join(d, "recipients.csv"), keep, fields)
    campaign._write_csv(os.path.join(d, "excluded.csv"), out, fields[1:] + ["Reason"])
    batches = (len(keep) + size - 1) // size
    campaign._write_json(_meta_path(name, mailing, root), {"id": mailing, "created": today.isoformat(), "list": os.path.basename(list_path) if list_path else "approved.csv",
                                                           "from": cfg["mail"]["from_email"], "batch_size": size, "batches": batches, "approvals": {}})
    campaign.log(name, "mail_plan", root, mailing=mailing, recipients=len(keep), excluded=len(out), batches=batches)
    info = preview(name, mailing, 1, root, today) if keep else None
    reasons = {}
    for r in out:
        k = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", r["Reason"]).split(" (")[0]
        reasons[k] = reasons.get(k, 0) + 1
    return {"recipients": len(keep), "excluded": len(out), "reasons": reasons, "batches": batches, "batch_size": size, "preview": info}


def _items(name, mailing, batch_no, root, cfg, today):
    """-> (items to send now, items left out now with a reason) for one batch, rendered from the saved template."""
    subject, body = read_template(os.path.join(mail_dir(name, mailing, root), "template.txt"))
    rows = [r for r in campaign._read_csv(os.path.join(mail_dir(name, mailing, root), "recipients.csv"))[0] if r["Batch"] == str(batch_no)]
    if not rows:
        raise SystemExit(f"Mailing {mailing} has no batch {batch_no}")
    ctx = context(name, root, cfg, mailing, today)
    items, out = [], []
    for r in rows:
        s, b, missing = render(subject, body, r, cfg)
        item = {"to": r["Email"], "lead_key": r["Lead Key"], "company": r["Company"], "subject": s, "body": b, "row": r}
        why = blocked(r, ctx, cfg) or ("missing " + ", ".join(missing) if missing else "")
        (out if why else items).append({**item, "reason": why} if why else item)
    return items, out


def _batch_hash(items, cfg):
    h = hashlib.sha256()
    for it in sorted(items, key=lambda x: x["to"]):
        h.update(mailer.digest(it["to"], it["subject"], it["body"], cfg).encode() + b"\n")
    return h.hexdigest()[:12]


def preview(name, mailing, batch_no, root=campaign.ROOT, today=None):
    """The dry run a person reads before approving: count, flags, rendered samples with headers, every recipient. Sends nothing."""
    spec = campaign.load(name, root)
    cfg = load_cfg(name, root)
    today = today or dt.date.today()
    meta = load_mailing(name, mailing, root)
    items, out = _items(name, mailing, batch_no, root, cfg, today)
    digest = _batch_hash(items, cfg)
    cap, used = mailer.cap_today(root, cfg, today)
    w = spec["outreach"].get("send_window", {})
    problems = mailer.sender_problems(cfg) + (mailer.subject_problems(items[0]["subject"]) if items else [])
    bad = mailer.health(name, root, cfg, today)
    picks = items[:1] + items[-1:] + items[1:-1][:: max(1, len(items) // SAMPLES)]
    picks = list({it["to"]: it for it in picks}.values())[:SAMPLES]
    lines = [f"# Mailing {mailing}, batch {batch_no} of {meta['batches']}  (hash `{digest}`)", "",
             f"{len(items)} emails from {cfg['sender']['name']} <{cfg['mail']['from_email']}>, provider {cfg['mail']['provider']}.",
             f"Today's cap {cap} ({used} already sent today); window {'/'.join(w.get('days', []))} {w.get('start', '')}-{w.get('end', '')} "
             f"{mailer.timezone(cfg, spec).key}; pause {cfg['mail']['delay_seconds'][0]}-{cfg['mail']['delay_seconds'][1]} s between emails.",
             "Nothing is sent by this preview.", ""]
    if problems or bad:
        lines += ["## Blocking"] + [f"* {p}" for p in problems + ([bad] if bad else [])] + [""]
    if len(items) > cap:
        lines += [f"**More emails than today's cap ({len(items)} > {cap}).** The rest wait for the next day's run.", ""]
    if out:
        lines += ["## Left out now (re-checked again right before each email)"] + [f"* {o['company']} <{o['to']}>: {o['reason']}" for o in out] + [""]
    lines += ["## Samples, exactly as they will be sent", ""]
    for it in picks:
        msg = mailer.build(cfg, it["to"], it["subject"], it["body"])
        hdr = "\n".join(f"{k}: {msg[k]}" for k in ("From", "To", "Reply-To", "Subject", "List-Unsubscribe") if msg[k])
        lines += ["```", hdr, "", it["body"].rstrip(), "```", ""]
    lines += ["## Recipients", ""] + [f"* {it['company']} <{it['to']}>" for it in items]
    lines += ["", f"Approve with: `leadengine campaign mail approve {name} {mailing} --batch {batch_no} --hash {digest}`",
              f"Then send with: `leadengine campaign mail send {name} {mailing} --batch {batch_no}` (add --dry-run first to write the emails to a folder)"]
    path = os.path.join(mail_dir(name, mailing, root), f"batch-{batch_no:02d}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    campaign.log(name, "mail_preview", root, mailing=mailing, batch=batch_no, count=len(items), left_out=len(out), hash=digest)
    return {"path": path, "hash": digest, "count": len(items), "left_out": len(out), "blocking": problems + ([bad] if bad else [])}


def approve(name, mailing, batch_no, expect_hash, root=campaign.ROOT, today=None):
    info = preview(name, mailing, batch_no, root, today)
    if info["hash"] != expect_hash:
        raise SystemExit(f"The batch changed since you read it (now {info['hash']}, you approved {expect_hash}). Read {info['path']} again.")
    if info["blocking"]:
        raise SystemExit("Blocking problems:\n  - " + "\n  - ".join(info["blocking"]))
    if not info["count"]:
        raise SystemExit("Nobody in this batch can be sent to now")
    cfg = load_cfg(name, root)
    items, _ = _items(name, mailing, batch_no, root, cfg, today or dt.date.today())
    meta = load_mailing(name, mailing, root)
    meta["approvals"][str(batch_no)] = {"hash": expect_hash, "at": dt.datetime.now().isoformat(timespec="seconds"),
                                        "items": {it["to"]: mailer.digest(it["to"], it["subject"], it["body"], cfg) for it in items}}
    campaign._write_json(_meta_path(name, mailing, root), meta)
    campaign.log(name, "mail_approve", root, mailing=mailing, batch=batch_no, approved=len(items), hash=expect_hash)
    return len(items)


def send(name, mailing, batch_no, root=campaign.ROOT, provider_name=None, dry_run=False, wait=False, prov=None, clock=None, sleep=None,
         today=None, out=print):
    """Sends an approved batch. Only addresses in the approval, with exactly the content approved, and still allowed right now."""
    spec = campaign.load(name, root)
    cfg = load_cfg(name, root)
    meta = load_mailing(name, mailing, root)
    appr = meta["approvals"].get(str(batch_no))
    if not appr:
        raise SystemExit(f"Batch {batch_no} is not approved. Read the preview, then: leadengine campaign mail approve {name} {mailing} "
                         f"--batch {batch_no} --hash HASH")
    probs = mailer.sender_problems(cfg)
    if probs:
        raise SystemExit("Fix before sending:\n  - " + "\n  - ".join(probs))
    today = today or dt.date.today()
    items, _ = _items(name, mailing, batch_no, root, cfg, today)
    ok = [it for it in items if appr["items"].get(it["to"]) == mailer.digest(it["to"], it["subject"], it["body"], cfg)]
    changed = len(items) - len(ok)
    if not ok:
        raise SystemExit("Nothing left to send in this batch" + (f" ({changed} changed since approval: preview and approve again)" if changed else ""))
    outbox = os.path.join(mail_dir(name, mailing, root), "outbox", f"batch-{batch_no:02d}")
    if prov is None:
        prov = mailer.provider("file" if dry_run else (provider_name or cfg["mail"]["provider"]), outbox, cfg)
    note = mailer.check_account(prov, cfg)
    if note:
        out("  note:", note)

    def recheck(it):                                   # opt-outs, replies and sends since the approval still count
        return blocked(it["row"], context(name, root, cfg, mailing, today), cfg)

    kw = {"clock": clock} if clock else {}
    if sleep:
        kw["sleep"] = sleep
    res = mailer.send_all(ok, prov, name=name, root=root, cfg=cfg, spec=spec, mailing=mailing, batch=str(batch_no), recheck=recheck,
                          wait=wait, out=out, **kw)
    res["changed_since_approval"] = changed
    res["outbox"] = outbox if prov.name == "file" else ""
    campaign.log(name, "mail_send", root, mailing=mailing, batch=batch_no, provider=prov.name, **{k: v for k, v in res.items() if k != "outbox"})
    return res


def test_send(name, mailing, to, root=campaign.ROOT, provider_name=None, prov=None, today=None):
    """One rendered sample (the first recipient's) sent only to one of your own addresses, with [TEST] in the subject."""
    cfg = load_cfg(name, root)
    own = {a.strip().lower() for a in (cfg["mail"]["from_email"], cfg["sender"].get("reply_email", ""), mailer.unsubscribe_address(cfg)) if a}
    if to.strip().lower() not in own:
        raise SystemExit(f"A test goes only to your own address ({', '.join(sorted(own))})")
    probs = mailer.sender_problems(cfg)
    if probs:
        raise SystemExit("Fix before sending:\n  - " + "\n  - ".join(probs))
    subject, body = read_template(os.path.join(mail_dir(name, mailing, root), "template.txt"))
    rows = campaign._read_csv(os.path.join(mail_dir(name, mailing, root), "recipients.csv"))[0]
    s, b, _ = render(subject, body, rows[0] if rows else {}, cfg)
    prov = prov or mailer.provider(provider_name or cfg["mail"]["provider"], os.path.join(mail_dir(name, mailing, root), "outbox", "test"), cfg)
    mailer.check_account(prov, cfg)
    try:
        mid = prov.send(mailer.build(cfg, to, "[TEST] " + s, b))
    finally:
        prov.close()
    campaign.log(name, "mail_test", root, mailing=mailing, to=to, provider=prov.name)
    return mid


def status(name, root=campaign.ROOT, mailing=None, today=None):
    cfg = load_cfg(name, root)
    today = today or dt.date.today()
    cap, used = mailer.cap_today(root, cfg, today)
    ledger = [r for r in mailer.read_ledger(root) if r["Campaign"] == name]
    d = os.path.join(campaign.folder(name, root), "mail")
    ids = [mailing] if mailing else sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x))) if os.path.isdir(d) else []
    rep = {"from": cfg["mail"]["from_email"], "cap_today": cap, "sent_today": used, "health": mailer.health(name, root, cfg, today), "mailings": {}}
    for m in ids:
        meta = load_mailing(name, m, root)
        recips = campaign._read_csv(os.path.join(mail_dir(name, m, root), "recipients.csv"))[0]
        rows = [r for r in ledger if r["Mailing"] == m]
        sent = {r["To"].lower() for r in rows if r["Status"] == mailer.SENT}
        rep["mailings"][m] = {"batches": {}, "recipients": len(recips), "sent": len(sent)}
        for b in range(1, meta["batches"] + 1):
            br = [r for r in recips if r["Batch"] == str(b)]
            st = {}
            for r in rows:
                if r["Batch"] == str(b):
                    st[r["Status"]] = st.get(r["Status"], 0) + 1
            rep["mailings"][m]["batches"][b] = {"size": len(br), "approved": str(b) in meta["approvals"],
                                               "sent": sum(1 for r in br if r["Email"].lower() in sent), "log": st}
    return rep


def main(argv, root):
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="leadengine campaign mail", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("name")
    p.add_argument("mailing")
    p.add_argument("--template", required=True)
    p.add_argument("--list", help="CSV of contacts instead of approved.csv (needs Email; Company, First Name, City, Email Status help)")
    for c in ("preview", "approve", "send"):
        p = sub.add_parser(c)
        p.add_argument("name")
        p.add_argument("mailing")
        p.add_argument("--batch", type=int, default=1)
    sub.choices["approve"].add_argument("--hash", required=True)
    s = sub.choices["send"]
    s.add_argument("--provider", help="smtp, gmail or file (default: config mail.provider)")
    s.add_argument("--dry-run", action="store_true", help="write the emails to a folder instead of sending")
    s.add_argument("--wait", action="store_true", help="if the send window is closed, wait for it to open (keep the computer awake)")
    s.add_argument("--yes", action="store_true", help="skip the typed confirmation (only when a person has said to send)")
    p = sub.add_parser("test")
    p.add_argument("name")
    p.add_argument("mailing")
    p.add_argument("--to", required=True)
    p.add_argument("--provider")
    p = sub.add_parser("status")
    p.add_argument("name")
    p.add_argument("mailing", nargs="?")
    p = sub.add_parser("sync", help="read replies, opt-outs and bounces back from the mailbox")
    p.add_argument("name")
    p.add_argument("--provider", default="gmail", choices=["gmail", "imap"])
    p.add_argument("--since", help="YYYY-MM-DD (default: the first send)")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        r = plan(a.name, a.mailing, a.template, root, a.list)
        print(f"{r['recipients']} recipients in {r['batches']} batch(es) of up to {r['batch_size']}; {r['excluded']} left out {r['reasons']}")
        if r["preview"]:
            print(f"Read batch 1: {r['preview']['path']} (hash {r['preview']['hash']})")
    elif a.cmd == "preview":
        r = preview(a.name, a.mailing, a.batch, root)
        print(f"{r['count']} emails, {r['left_out']} left out, hash {r['hash']}\nRead: {r['path']}")
        for x in r["blocking"]:
            print("  blocking:", x)
    elif a.cmd == "approve":
        n = approve(a.name, a.mailing, a.batch, a.hash, root)
        print(f"Approved {n} emails. Send with: leadengine campaign mail send {a.name} {a.mailing} --batch {a.batch}")
    elif a.cmd == "send":
        if not a.dry_run and not a.yes:
            cfg = load_cfg(a.name, root)
            meta = load_mailing(a.name, a.mailing, root)
            n = len(meta["approvals"].get(str(a.batch), {}).get("items", {}))
            prompt = (f"Send up to {n} approved emails from {cfg['mail']['from_email']} via {a.provider or cfg['mail']['provider']} "
                      f"(mailing {a.mailing}, batch {a.batch})? Type SEND to go ahead: ")
            if not sys.stdin.isatty():
                raise SystemExit("Refusing to send without a person at the keyboard: run it in a terminal, or add --yes when you have decided to send")
            if input(prompt).strip() != "SEND":
                raise SystemExit("Not sent.")
        r = send(a.name, a.mailing, a.batch, root, a.provider, a.dry_run, a.wait)
        verb = "written to " + r["outbox"] if r["outbox"] else "sent"
        print(f"{r['sent']} {verb}; {r['skipped']} skipped; {r['failed']} failed ({r['bounced']} bounced)")
        if r["changed_since_approval"]:
            print(f"  note: {r['changed_since_approval']} changed since approval and were not sent (preview and approve again)")
        if r["stopped"]:
            print("  stopped:", r["stopped"])
    elif a.cmd == "test":
        print("Test sent:", test_send(a.name, a.mailing, a.to, root, a.provider))
    elif a.cmd == "sync":
        from . import replies
        r = replies.sync(a.name, root, a.provider, dt.date.fromisoformat(a.since) if a.since else None)
        imp = r["import"] or {}
        print(f"{r['found']} messages read, {r['events']} events; {len(imp.get('suppressed_added', []))} added to suppress.csv; "
              f"{imp.get('tasks_stopped', 0)} planned tasks stopped")
    else:
        print(json.dumps(status(a.name, root, a.mailing), indent=2))
    return 0
