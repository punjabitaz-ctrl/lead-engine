"""Deal pipeline for a campaign: from first reply to a won, delivered project. One row per deal in campaigns/<name>/pipeline.csv.

  Contacted -> Replied -> Call booked -> Proposal sent -> Won -> Delivered      (or Lost, with a reason)

Rules encoded from the seller's offer (spec.offer):
  * products have fixed prices; Won defaults to the product price
  * capacity_per_week caps how many projects start in an ISO week; the report warns when it is full
  * in-person visits are never part of the outreach sequence. A deal unlocks one only when its MONTHLY value reaches
    offer.in_person_min_monthly_value (default 5000)."""
import csv
import datetime as dt
import os

from . import campaign

STAGES = ["Contacted", "Replied", "Call booked", "Proposal sent", "Won", "Delivered", "Lost"]
FIELDS = ["Deal ID", "Lead Key", "Company", "Contact", "Product", "Stage", "One-time $", "Monthly $", "Source", "Signal", "First channel",
          "Created", "Updated", "Won date", "Lost reason", "Furthest", "Notes"]
PATH = "pipeline.csv"


def _path(name, root):
    return os.path.join(campaign.folder(name, root), PATH)


def _load(name, root):
    return campaign._read_csv(_path(name, root))[0]


def _save(name, root, rows):
    campaign._write_csv(_path(name, root), rows, FIELDS)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def in_person_eligible(deal, spec):
    return _num(deal.get("Monthly $")) >= spec["offer"]["in_person_min_monthly_value"]


def add_deal(name, product=None, lead_key="", company="", contact="", first_channel="email", monthly=0, notes="", root=campaign.ROOT, today=None):
    spec = campaign.load(name, root)
    today = today or dt.date.today()
    products = {p["id"]: p for p in spec["offer"]["products"]}
    if product and product not in products:
        raise SystemExit(f"Unknown product {product!r}. Products: {', '.join(products)}")
    src = sig = ""
    if lead_key:
        match = [r for r in campaign._read_csv(os.path.join(campaign.folder(name, root), "approved.csv"))[0] if r["Lead Key"] == lead_key]
        if not match:
            raise SystemExit(f"Lead key {lead_key!r} is not in approved.csv. Only approved leads enter the pipeline.")
        m = match[0]
        company, contact = company or m["Company"], contact or " ".join(x for x in (m.get("First Name"), m.get("Last Name")) if x)
        src, sig = m.get("Source", ""), m.get("Primary Signal", "")
    if not company:
        raise SystemExit("Give --lead-key (an approved lead) or --company")
    rows = _load(name, root)
    deal = {"Deal ID": f"D{len(rows) + 1:03d}", "Lead Key": lead_key, "Company": company, "Contact": contact, "Product": product or "",
            "Stage": "Contacted", "One-time $": "", "Monthly $": monthly or "", "Source": src, "Signal": sig, "First channel": first_channel,
            "Created": today.isoformat(), "Updated": today.isoformat(), "Won date": "", "Lost reason": "", "Furthest": "Contacted", "Notes": notes}
    _save(name, root, rows + [deal])
    campaign.log(name, "deal_add", root, deal=deal["Deal ID"], company=company)
    return deal


def move_deal(name, deal_id, stage, one_time=None, monthly=None, reason="", notes="", root=campaign.ROOT, today=None):
    if stage not in STAGES:
        raise SystemExit(f"Stage must be one of: {', '.join(STAGES)}")
    spec = campaign.load(name, root)
    today = today or dt.date.today()
    rows = _load(name, root)
    deal = next((r for r in rows if r["Deal ID"] == deal_id), None)
    if not deal:
        raise SystemExit(f"No deal {deal_id}")
    if stage == "Lost" and not reason:
        raise SystemExit("Lost needs a reason (--reason): it is the most useful data in the pipeline")
    if stage == "Won":
        if not deal["Product"] and one_time is None:
            raise SystemExit("Won needs a product on the deal or --one-time")
        price = next((p["price"] for p in spec["offer"]["products"] if p["id"] == deal["Product"]), 0)
        deal["One-time $"] = one_time if one_time is not None else (deal["One-time $"] or price)
        deal["Won date"] = today.isoformat()
    elif one_time is not None:
        deal["One-time $"] = one_time
    if monthly is not None:
        deal["Monthly $"] = monthly
    deal.update(Stage=stage, Updated=today.isoformat(), **({"Lost reason": reason} if reason else {}))
    if stage != "Lost" and STAGES.index(stage) > STAGES.index(deal["Furthest"] or "Contacted"):
        deal["Furthest"] = stage
    if notes:
        deal["Notes"] = (deal["Notes"] + " | " if deal["Notes"] else "") + notes
    _save(name, root, rows)
    campaign.log(name, "deal_move", root, deal=deal_id, stage=stage)
    return deal, in_person_eligible(deal, spec)


def report(name, root=campaign.ROOT, today=None):
    spec = campaign.load(name, root)
    today = today or dt.date.today()
    rows = _load(name, root)
    top = {s: i for i, s in enumerate(STAGES[:-1])}               # Lost is not a step; a lost deal counts at its furthest stage
    funnel = {s: sum(1 for r in rows if top.get(r["Furthest"] or "Contacted", 0) >= i) for s, i in top.items()}
    steps = list(top)
    conv = {f"{x} -> {y}": (round(funnel[y] / funnel[x], 2) if funnel[x] else None) for x, y in zip(steps[:-1], steps[1:])}
    won = [r for r in rows if r["Stage"] in ("Won", "Delivered")]
    week = today.isocalendar()[:2]
    started = [r for r in won if r["Won date"] and dt.date.fromisoformat(r["Won date"]).isocalendar()[:2] == week]
    cap = spec["offer"]["capacity_per_week"]
    by = {}
    for key in ("Source", "Signal", "First channel"):
        for r in rows:
            b = by.setdefault(f"{key}: {r[key] or '(none)'}", [0, 0])
            b[0] += 1
            b[1] += r["Stage"] in ("Won", "Delivered")
    return {"deals": len(rows), "by_stage": {s: sum(1 for r in rows if r["Stage"] == s) for s in STAGES}, "funnel_reached": funnel,
            "conversion": conv, "won": len(won), "one_time_revenue": sum(_num(r["One-time $"]) for r in won),
            "monthly_recurring": sum(_num(r["Monthly $"]) for r in won), "lost_reasons": sorted({r["Lost reason"] for r in rows if r["Lost reason"]}),
            "capacity": {"per_week": cap, "started_this_week": len(started), "full": len(started) >= cap},
            "in_person_eligible": [r["Deal ID"] + " " + r["Company"] for r in rows if r["Stage"] not in ("Lost", "Delivered") and in_person_eligible(r, spec)],
            "win_rate_by": {k: f"{w}/{n}" for k, (n, w) in sorted(by.items())}}
