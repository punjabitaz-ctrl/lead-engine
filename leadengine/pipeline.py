"""Deal pipeline for a campaign: from first reply to a delivered project. One row per deal in campaigns/<name>/pipeline.csv.

  Contacted -> Replied -> Call booked -> Proposal sent -> Won -> In build -> Delivered      (or Lost, with a reason)

Rules encoded from the seller's offer (spec.offer):
  * Won = the client agreed and signed. Work does NOT start until `deal start`, which requires
      - payment as the product demands (single page: paid in full; 3-page: the deposit, 50%), and
      - a complete intake (every item in offer.intake_required supplied by the client)
  * capacity_per_week caps how many projects START in an ISO week; the report warns when it is full
  * in-person visits are never part of the outreach sequence. A deal unlocks one only when its MONTHLY value reaches
    offer.in_person_min_monthly_value (default 5000)."""
import datetime as dt
import os

from . import campaign

STAGES = ["Contacted", "Replied", "Call booked", "Proposal sent", "Won", "In build", "Delivered", "Lost"]
BOOKED = ("Won", "In build", "Delivered")
FIELDS = ["Deal ID", "Lead Key", "Company", "Contact", "Product", "Plan", "Stage", "One-time $", "Paid $", "Monthly $", "Intake complete",
          "Source", "Signal", "First channel", "Created", "Updated", "Won date", "Launch price", "Price lock until", "Start date", "Call required", "Lost reason", "Furthest", "Notes"]
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


def _product(spec, pid):
    return next((p for p in spec["offer"]["products"] if p["id"] == pid), None)


def _plan(spec, pid):
    return next((p for p in spec["offer"].get("plans", []) if p["id"] == pid), None)


def amount_due_to_start(deal, spec):
    """Dollars that must be paid before work starts: the full price, or the deposit share the product requires."""
    prod = _product(spec, deal["Product"])
    price = _num(deal["One-time $"]) or (prod["price"] if prod else 0)
    pay = (prod or {}).get("payment", {"type": "full_upfront"})
    return price * (pay.get("percent", 50) / 100.0) if pay["type"] == "deposit" else price


def in_person_eligible(deal, spec):
    return _num(deal.get("Monthly $")) >= spec["offer"]["in_person_min_monthly_value"]


def add_deal(name, product=None, lead_key="", company="", contact="", first_channel="email", monthly=0, notes="", plan="", root=campaign.ROOT, today=None):
    spec = campaign.load(name, root)
    today = today or dt.date.today()
    if product and not _product(spec, product):
        raise SystemExit(f"Unknown product {product!r}. Products: {', '.join(p['id'] for p in spec['offer']['products'])}")
    if plan and not _plan(spec, plan):
        raise SystemExit(f"Unknown plan {plan!r}. Plans: {', '.join(p['id'] for p in spec['offer'].get('plans', []))}")
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
    deal = dict.fromkeys(FIELDS, "")
    deal.update({"Deal ID": f"D{len(rows) + 1:03d}", "Lead Key": lead_key, "Company": company, "Contact": contact, "Product": product or "", "Plan": plan,
                 "Stage": "Contacted", "Monthly $": monthly or "", "Intake complete": "N", "Paid $": 0, "Source": src, "Signal": sig,
                 "First channel": first_channel, "Created": today.isoformat(), "Updated": today.isoformat(), "Furthest": "Contacted", "Notes": notes})
    _save(name, root, rows + [deal])
    campaign.log(name, "deal_add", root, deal=deal["Deal ID"], company=company)
    return deal


def _find(rows, deal_id):
    deal = next((r for r in rows if r["Deal ID"] == deal_id), None)
    if not deal:
        raise SystemExit(f"No deal {deal_id}")
    return deal


def move_deal(name, deal_id, stage, one_time=None, monthly=None, reason="", notes="", plan=None, root=campaign.ROOT, today=None):
    if stage not in STAGES:
        raise SystemExit(f"Stage must be one of: {', '.join(STAGES)}")
    if stage == "In build":
        raise SystemExit("Use `deal start`: it checks payment and intake before work begins")
    spec = campaign.load(name, root)
    today = today or dt.date.today()
    rows = _load(name, root)
    deal = _find(rows, deal_id)
    if stage == "Lost" and not reason:
        raise SystemExit("Lost needs a reason (--reason): it is the most useful data in the pipeline")
    if plan:
        if not _plan(spec, plan):
            raise SystemExit(f"Unknown plan {plan!r}")
        deal["Plan"] = plan
    if stage == "Won":
        prod = _product(spec, deal["Product"])
        if not prod and one_time is None:
            raise SystemExit("Won needs a product on the deal or --one-time")
        deal["One-time $"] = one_time if one_time is not None else (deal["One-time $"] or prod["price"])
        deal["Won date"] = today.isoformat()
        lau = spec["offer"]["launch"]
        taken = sum(1 for r in rows if r["Launch price"] == "Y")
        if campaign.in_launch(spec, today) and taken < lau.get("max_customers", 100):
            deal["Launch price"] = "Y"
            deal["Price lock until"] = str(campaign.add_months(today, lau["lock_months"])) if lau.get("lock_months") is not None else "TBD"
        if deal["Plan"] and not _num(deal["Monthly $"]) and monthly is None:
            deal["Monthly $"] = _plan(spec, deal["Plan"])["price"]
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


def require_call(name, deal_id, reason, root=campaign.ROOT, today=None):
    """Calls are off by default (outreach.phone_policy). This records the one reason a call is absolutely required."""
    rows = _load(name, root)
    deal = _find(rows, deal_id)
    deal["Call required"] = reason
    deal["Updated"] = (today or dt.date.today()).isoformat()
    _save(name, root, rows)
    campaign.log(name, "call_required", root, deal=deal_id, reason=reason)
    return deal


def record_payment(name, deal_id, amount, root=campaign.ROOT, today=None):
    rows = _load(name, root)
    deal = _find(rows, deal_id)
    deal["Paid $"] = _num(deal["Paid $"]) + float(amount)
    deal["Updated"] = (today or dt.date.today()).isoformat()
    _save(name, root, rows)
    campaign.log(name, "payment", root, deal=deal_id, amount=float(amount))
    return deal


def mark_intake(name, deal_id, complete=True, root=campaign.ROOT, today=None):
    rows = _load(name, root)
    deal = _find(rows, deal_id)
    deal["Intake complete"] = "Y" if complete else "N"
    deal["Updated"] = (today or dt.date.today()).isoformat()
    _save(name, root, rows)
    campaign.log(name, "intake", root, deal=deal_id, complete=complete)
    return deal


def start_work(name, deal_id, root=campaign.ROOT, today=None):
    """Starts the 72-hour clock. Refuses until the deal is Won, paid as required, and the intake is complete."""
    spec = campaign.load(name, root)
    rows = _load(name, root)
    deal = _find(rows, deal_id)
    missing = []
    if deal["Stage"] != "Won":
        missing.append(f"deal is {deal['Stage']!r}; it must be Won (agreement signed)")
    due = amount_due_to_start(deal, spec)
    if _num(deal["Paid $"]) < due:
        missing.append(f"payment: ${_num(deal['Paid $']):,.2f} received, ${due:,.2f} required before work starts")
    if deal["Intake complete"] != "Y":
        missing.append("intake is not complete: " + ", ".join(spec["offer"]["intake_required"]))
    if missing:
        raise SystemExit("Work cannot start yet:\n  - " + "\n  - ".join(missing))
    today = today or dt.date.today()
    limit = spec["offer"].get("max_parallel_builds", 3)
    if sum(1 for r in rows if r["Stage"] == "In build") >= limit:
        raise SystemExit(f"{limit} projects are already in build (offer.max_parallel_builds). Deliver one first, then start this one.")
    deal.update(Stage="In build", **{"Start date": today.isoformat(), "Updated": today.isoformat(), "Furthest": "In build"})
    _save(name, root, rows)
    campaign.log(name, "work_started", root, deal=deal_id)
    return deal


def report(name, root=campaign.ROOT, today=None):
    spec = campaign.load(name, root)
    today = today or dt.date.today()
    rows = _load(name, root)
    top = {s: i for i, s in enumerate(STAGES[:-1])}               # Lost is not a step; a lost deal counts at its furthest stage
    funnel = {s: sum(1 for r in rows if top.get(r["Furthest"] or "Contacted", 0) >= i) for s, i in top.items()}
    steps = list(top)
    conv = {f"{x} -> {y}": (round(funnel[y] / funnel[x], 2) if funnel[x] else None) for x, y in zip(steps[:-1], steps[1:])}
    booked = [r for r in rows if r["Stage"] in BOOKED]
    week = today.isocalendar()[:2]
    started = [r for r in rows if r["Start date"] and dt.date.fromisoformat(r["Start date"]).isocalendar()[:2] == week]
    cap = campaign.effective_capacity(spec)
    by = {}
    for key in ("Source", "Signal", "First channel", "Plan"):
        for r in rows:
            b = by.setdefault(f"{key}: {r[key] or '(none)'}", [0, 0])
            b[0] += 1
            b[1] += r["Stage"] in BOOKED
    return {"deals": len(rows), "by_stage": {s: sum(1 for r in rows if r["Stage"] == s) for s in STAGES}, "funnel_reached": funnel,
            "conversion": conv, "booked": len(booked), "one_time_booked": sum(_num(r["One-time $"]) for r in booked),
            "cash_collected": sum(_num(r["Paid $"]) for r in rows), "monthly_recurring_booked": sum(_num(r["Monthly $"]) for r in booked),
            "in_build": [f"{r['Deal ID']} {r['Company']}" for r in rows if r["Stage"] == "In build"], "max_parallel_builds": spec["offer"].get("max_parallel_builds", 3),
            "calls_needed": [f"{r['Deal ID']} {r['Company']}: {r['Call required']}" for r in rows if r["Call required"] and r["Stage"] not in ("Lost", "Delivered")],
            "launch_deals": sum(1 for r in rows if r["Launch price"] == "Y"),
            "waiting_to_start": [f"{r['Deal ID']} {r['Company']}" for r in rows if r["Stage"] == "Won"],
            "lost_reasons": sorted({r["Lost reason"] for r in rows if r["Lost reason"]}),
            "capacity": {"per_week": cap, "stated": spec["offer"]["capacity_per_week"], "started_this_week": len(started), "full": len(started) >= cap},
            "in_person_eligible": [r["Deal ID"] + " " + r["Company"] for r in rows if r["Stage"] not in ("Lost", "Delivered") and in_person_eligible(r, spec)],
            "booked_rate_by": {k: f"{w}/{n}" for k, (n, w) in sorted(by.items())}}
