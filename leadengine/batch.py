"""Batch approval: review one day's first-contact emails together instead of one at a time, then approve exactly what you reviewed.

  preview  -> outreach/batch-<date>-<channel>.md : counts, flags, samples, every recipient, and a batch hash
  approve  -> marks the batch Approved to send = Y, only if you pass the hash from the preview and nothing changed since
  export   -> outreach/send-<date>-<channel>.csv : To, Subject, Body for a mail merge or Gmail drafts (this tool still sends nothing)

A batch is every task for that date and channel that carries a draft (step 1 emails) and is not yet approved."""
import hashlib
import os
import re

from . import campaign

LEFTOVER = re.compile(r"\{[a-z_]+\}|\[[^\]]{2,}\]")
SAMPLE = 5


def _files(name, root):
    d = os.path.join(campaign.folder(name, root), "outreach")
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.startswith("tasks-")] if os.path.isdir(d) else []


def _batch(name, date, channel, root, include_approved=False):
    """-> [(file, rows, fields, row)] for the batch's rows."""
    out = []
    for path in _files(name, root):
        rows, fields = campaign._read_csv(path)
        for r in rows:
            if (r["Date"] == date and r["Channel"] == channel and r["Draft"].strip() and r.get("Done (Y/N)", "").strip().upper() != "STOPPED"
                    and (include_approved or r["Approved to send (Y/N)"].upper() != "Y")):
                out.append((path, rows, fields, r))
    return out


def _digest(rows):
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda r: r["Lead Key"]):
        h.update("|".join((r["Lead Key"], r["Where"], r["Subject"], r["Draft"])).encode("utf-8") + b"\n")
    return h.hexdigest()[:12]


def _flags(r, sup, seen):
    f = []
    if campaign.suppressed({"Email": r["Where"], "Company": r["Company"], "Website": "", "City": ""}, sup) or r["Lead Key"].lower() in sup:
        f.append("suppressed: do not send")
    if LEFTOVER.search(r["Draft"]) or LEFTOVER.search(r["Subject"]):
        f.append("leftover placeholder in the draft")
    if r["Draft"].startswith("Hi there"):
        f.append("no first name (reads 'Hi there')")
    if not r["Where"] or "@" not in r["Where"]:
        f.append("no valid email address")
    if r["Where"].lower() in seen:
        f.append("same address appears twice in this batch")
    seen.add(r["Where"].lower())
    return f


def preview(name, date, channel="email", root=campaign.ROOT):
    spec = campaign.load(name, root)
    items = _batch(name, date, channel, root)
    if not items:
        raise SystemExit(f"No unapproved drafts for {channel} on {date}. Plan outreach first: leadengine campaign outreach {name} --start {date}")
    rows = [r for _, _, _, r in items]
    sup = campaign.load_suppressions(name, root)
    seen, flagged = set(), {}
    for r in rows:
        f = _flags(r, sup, seen)
        if f:
            flagged[r["Lead Key"]] = f
    cap = spec["outreach"]["daily_caps"].get(channel, 0)
    digest = _digest(rows)
    picks = {rows[0]["Lead Key"], rows[-1]["Lead Key"], *flagged}
    picks |= {r["Lead Key"] for r in rows[::10]}
    sample = [r for r in rows if r["Lead Key"] in picks][: SAMPLE + len(flagged)]
    lines = [f"# Batch {date} / {channel}  (hash `{digest}`)", "",
             f"{len(rows)} drafts, daily cap {cap}, {len(flagged)} flagged. Nothing is sent by this tool.", ""]
    if len(rows) > cap:
        lines += [f"**Over the daily cap ({len(rows)} > {cap}).** Re-plan or split the batch.", ""]
    if flagged:
        lines += ["## Flagged (these are left out if you approve with --exclude-flagged)"] + [f"* {k}: {'; '.join(v)}" for k, v in flagged.items()] + [""]
    lines += ["## Drafts to read (first, last, every flagged one, and every 10th)", ""]
    for r in sample:
        lines += [f"### {r['Company']}  <{r['Where']}>", f"**Subject:** {r['Subject']}", "", r["Draft"], "", "---", ""]
    lines += ["## Recipients", ""] + [f"* {r['Company']} <{r['Where']}>" for r in rows]
    lines += ["", f"Approve with: `leadengine campaign batch approve {name} {date} --hash {digest}`" + (" --exclude-flagged" if flagged else "")]
    path = os.path.join(campaign.folder(name, root), "outreach", f"batch-{date}-{channel}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    campaign.log(name, "batch_preview", root, date=date, channel=channel, count=len(rows), flagged=len(flagged), hash=digest)
    return {"path": path, "hash": digest, "count": len(rows), "flagged": flagged, "over_cap": len(rows) > cap}


def approve(name, date, expect_hash, channel="email", exclude_flagged=False, root=campaign.ROOT):
    info = preview(name, date, channel, root)                          # recomputes everything from the files as they are now
    if info["hash"] != expect_hash:
        raise SystemExit(f"The batch changed since you read it (now {info['hash']}, you approved {expect_hash}). Read {info['path']} again.")
    if info["over_cap"]:
        raise SystemExit("The batch is over the daily cap; re-plan before approving")
    hard = {k: v for k, v in info["flagged"].items()}
    if hard and not exclude_flagged:
        raise SystemExit("Flagged drafts block approval. Fix them, or approve the rest with --exclude-flagged:\n  - " +
                         "\n  - ".join(f"{k}: {'; '.join(v)}" for k, v in hard.items()))
    changed, files = 0, {}
    for path, rows, fields, r in _batch(name, date, channel, root):
        if r["Lead Key"] in hard:
            continue
        r["Approved to send (Y/N)"] = "Y"
        changed += 1
        files[path] = (rows, fields)
    for path, (rows, fields) in files.items():
        campaign._write_csv(path, rows, fields)
    campaign.log(name, "batch_approve", root, date=date, channel=channel, approved=changed, left_out=len(hard), hash=expect_hash)
    return changed, len(hard)


def export_approved(name, date, channel="email", root=campaign.ROOT):
    sup = campaign.load_suppressions(name, root)
    out_rows, seen = [], set()
    for _, _, _, r in _batch(name, date, channel, root, include_approved=True):
        if r["Approved to send (Y/N)"].upper() != "Y" or r["Done (Y/N)"].upper() == "Y":
            continue
        if _flags(r, sup, seen):
            continue
        out_rows.append({"To": r["Where"], "Subject": r["Subject"], "Body": r["Draft"], "Send window": r.get("Window", ""), "Company": r["Company"], "Lead Key": r["Lead Key"]})
    if not out_rows:
        raise SystemExit("Nothing approved and unsent for that date")
    path = os.path.join(campaign.folder(name, root), "outreach", f"send-{date}-{channel}.csv")
    campaign._write_csv(path, out_rows, ["To", "Subject", "Body", "Send window", "Company", "Lead Key"])
    campaign.log(name, "batch_export", root, date=date, channel=channel, rows=len(out_rows))
    return path, len(out_rows)
