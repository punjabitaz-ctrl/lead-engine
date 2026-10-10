"""Campaign layer: one folder per market-and-offer, a fixed pipeline, and a human gate before anything is contacted.

  define -> discover -> REVIEW GATE -> outreach plan -> (humans send) -> engagement

  campaigns/<name>/spec.json      geography, vertical pack, sources, stage sizes, outreach sequence
  campaigns/<name>/config.json    sender, offer and scoring overrides (passed to the engine as --config)
  campaigns/<name>/review/        lead packs for a human to mark Keep / Drop / Unsure
  campaigns/<name>/approved.csv   leads a human kept (the only input to outreach planning)
  campaigns/<name>/outreach/      dated task lists; nothing is sent by this tool
  campaigns/<name>/audit.log      one JSON line per action

Commands: init, list, validate, status, run, approve, outreach. `status --json` is the entry point for an agent."""
import argparse
import copy
import csv
import datetime as dt
import json
import os
import re
import sys

from . import config, geo, keys, packs
from .filters import norm_name

ROOT = "campaigns"
SOURCES = {"nppes", "places", "adzuna", "csv", "manual"}
CHANNELS = {"email", "phone", "linkedin"}
DECISIONS = {"keep": "Keep", "drop": "Drop", "unsure": "Unsure"}
PLACEHOLDER = re.compile(r"\[[^\]]+\]")

DEFAULT_SPEC = {
    "name": "",
    "geography": {"state": "", "counties": [], "cities": []},
    "vertical": "healthcare-practices",
    "tiers": ["focus"],
    "sources": [],
    "industry": "",
    "signal": "any",
    "stages": [59, 100, 250],
    "template": "lead-engine-template.xlsx",
    "outreach": {
        "daily_caps": {"email": 20, "phone": 10, "linkedin": 15},
        "sequence": [
            {"day": 0, "channel": "email", "action": "Send the approved email 1"},
            {"day": 3, "channel": "linkedin", "action": "Connect with a short note; engage with a recent post"},
            {"day": 5, "channel": "email", "action": "Follow-up 1: one new angle, two sentences"},
            {"day": 8, "channel": "phone", "action": "Call; check the Do-Not-Call list first"},
            {"day": 14, "channel": "email", "action": "Last note: offer to close the loop"},
        ],
    },
}


# ---- paths and small helpers ---------------------------------------------
def folder(name, root=ROOT):
    return os.path.join(root, name)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path):
    if not os.path.exists(path):
        return [], []
    with open(path, newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        return list(r), list(r.fieldnames or [])


def _write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def log(name, event, root=ROOT, **details):
    with open(os.path.join(folder(name, root), "audit.log"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"), "event": event, **details}) + "\n")


def lead_key(row):
    return keys.dedupe_key(row.get("Website", ""), row.get("Company", ""), row.get("City", ""))


# ---- define ---------------------------------------------------------------
def init(name, state, counties=(), cities=(), vertical="healthcare-practices", tiers=("focus",), root=ROOT):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise SystemExit("Campaign names use lower-case letters, digits and hyphens, e.g. nj-dental")
    d = folder(name, root)
    if os.path.exists(d):
        raise SystemExit(f"{d} already exists")
    pack = packs.load(vertical)
    spec = copy.deepcopy(DEFAULT_SPEC)
    spec.update(name=name, vertical=vertical, tiers=list(tiers), sources=list(pack["sources"]), industry=pack.get("industry", ""))
    spec["geography"] = {"state": state.upper(), "counties": list(counties), "cities": list(cities)}
    _write_json(os.path.join(d, "spec.json"), spec)
    cfg = {"sender": copy.deepcopy(config.DEFAULTS["sender"])}
    cfg["_note"] = "Fill in the sender block before outreach planning. Add any other config.DEFAULTS keys to override scoring."
    _write_json(os.path.join(d, "config.json"), cfg)
    log(name, "init", root, geography=spec["geography"], vertical=vertical)
    problems = validate(spec)
    return spec, problems


def load(name, root=ROOT):
    path = os.path.join(folder(name, root), "spec.json")
    if not os.path.exists(path):
        raise SystemExit(f"No campaign {name!r} (looked for {path}). Create one with: leadengine campaign init {name} --state NJ ...")
    return _read_json(path)


def validate(spec):
    """Returns a list of problems; empty means the spec can run."""
    bad = []
    g = spec.get("geography", {})
    try:
        places = geo.resolve(g)
        if not places:
            bad.append("geography resolves to no places")
    except SystemExit as exc:
        bad.append(f"geography: {exc}")
    try:
        pack = packs.load(spec.get("vertical", ""))
        for t in spec.get("tiers", []):
            if t != "all" and t not in pack["tiers"]:
                bad.append(f"tier {t!r} is not in pack {pack['id']!r} (has: {', '.join(pack['tiers'])})")
    except SystemExit as exc:
        bad.append(str(exc))
    for s in spec.get("sources", []):
        if s not in SOURCES:
            bad.append(f"unknown source {s!r}")
    if not spec.get("sources"):
        bad.append("no sources")
    if not spec.get("stages") or any((not isinstance(n, int)) or n < 1 for n in spec["stages"]):
        bad.append("stages must be positive whole numbers, e.g. [59, 100, 250]")
    seq, last = spec.get("outreach", {}).get("sequence", []), -1
    for i, st in enumerate(seq, 1):
        if st.get("channel") not in CHANNELS:
            bad.append(f"outreach step {i}: channel must be one of {sorted(CHANNELS)}")
        if not isinstance(st.get("day"), int) or st["day"] < last:
            bad.append(f"outreach step {i}: 'day' must be a whole number, not earlier than the previous step")
        else:
            last = st["day"]
    for ch in {s.get("channel") for s in seq}:
        if ch in CHANNELS and not spec["outreach"].get("daily_caps", {}).get(ch):
            bad.append(f"outreach: set daily_caps for {ch}")
    return bad


def blockers(spec):
    """Things a human must provide before the next stage can work (keys). Network reachability is checked by `leadengine doctor`."""
    out = []
    for src, var, why in (("places", "GOOGLE_PLACES_API_KEY", "Google Places key"), ("adzuna", "ADZUNA_APP_ID", "Adzuna id"),
                          ("adzuna", "ADZUNA_APP_KEY", "Adzuna key")):
        if src in spec.get("sources", []) and not os.environ.get(var):
            out.append(f"set {var} ({why}) for the {src} source")
    return out


# ---- discover -------------------------------------------------------------
REVIEW_EXTRA = ["Lead Key", "Decision", "Reviewer Notes"]


def run_discover(name, root=ROOT, target=None):
    """Runs the engine for the next stage size and turns its output into a review pack. Does not contact anyone."""
    from . import cli
    spec = load(name, root)
    problems = validate(spec)
    if problems:
        raise SystemExit("Spec problems:\n  - " + "\n  - ".join(problems))
    need = blockers(spec)
    if need:
        raise SystemExit("Blocked:\n  - " + "\n  - ".join(need))
    d = folder(name, root)
    pack = packs.load(spec["vertical"])
    g = spec["geography"]
    packs_done = len(_review_packs(name, root))
    size = target or spec["stages"][min(packs_done, len(spec["stages"]) - 1)]
    argv = ["run", "--no-prompt", "--target", str(size), "--signal", spec.get("signal", "any"), "--out", os.path.join(d, "runs"),
            "--state-dir", os.path.join(d, ".state"), "--config", os.path.join(d, "config.json"), "--template", spec["template"],
            "--state", g["state"]]
    for src in spec["sources"]:
        argv += ["--source", src]
    for c in g.get("counties", []):
        argv += ["--county", c]
    for c in g.get("cities", []):
        argv += ["--city", c if "," in c else f"{c}, {g['state']}"]
    tiers = spec.get("tiers") or ["focus"]
    tier_names = ["all"] if tiers == ["all"] else tiers
    if "nppes" in spec["sources"]:
        argv += ["--taxonomy", ",".join(packs.terms(pack, "taxonomies", tier_names))]
    for q in packs.terms(pack, "places_queries", tier_names):
        argv += ["--places-query", q]
    profs = packs.terms(pack, "professions", tier_names)
    if profs:
        argv += ["--profession", ",".join(profs)]
    if spec.get("industry"):
        argv += ["--industry", spec["industry"]]
    if "manual" in spec["sources"] or "csv" in spec["sources"]:
        raise SystemExit("manual and csv sources need a file: run `leadengine run ... --manual FILE` yourself, then pass the CSV to `campaign review-pack`.")
    written = cli.run(cli.build_parser().parse_args(argv))
    packs_out = []
    for path in written or []:
        packs_out.append(make_review_pack(name, path, root))
    log(name, "discover", root, target=size, produced=packs_out)
    return packs_out


def _review_packs(name, root=ROOT):
    d = os.path.join(folder(name, root), "review")
    return sorted(os.path.join(d, f) for f in os.listdir(d)) if os.path.isdir(d) else []


def make_review_pack(name, lead_csv, root=ROOT):
    rows, fields = _read_csv(lead_csv)
    for r in rows:
        r["Lead Key"], r["Decision"], r["Reviewer Notes"] = lead_key(r), "", ""
    out = os.path.join(folder(name, root), "review", f"pack-{len(_review_packs(name, root)) + 1:02d}.csv")
    _write_csv(out, rows, fields + REVIEW_EXTRA)
    return out


# ---- review gate ----------------------------------------------------------
def approve(name, reviewed_csv, root=ROOT):
    """Reads a pack a human marked up. Keep -> approved.csv, Drop -> rejected.csv, Unsure -> pending.csv. Blank rows are left for later."""
    rows, fields = _read_csv(reviewed_csv)
    if not rows:
        raise SystemExit(f"{reviewed_csv} has no rows")
    for need in ("Lead Key", "Decision"):
        if need not in fields:
            raise SystemExit(f"{reviewed_csv} is missing the {need!r} column: use a pack from {folder(name, root)}/review/")
    errors = [f"row {i}: Decision {r['Decision']!r} is not Keep, Drop or Unsure" for i, r in enumerate(rows, 2)
              if r["Decision"].strip() and r["Decision"].strip().lower() not in DECISIONS]
    if errors:
        raise SystemExit("Fix these rows and run again:\n  - " + "\n  - ".join(errors))
    d = folder(name, root)
    got = {"Keep": [], "Drop": [], "Unsure": [], "": []}
    for r in rows:
        dec = DECISIONS.get(r["Decision"].strip().lower(), "")
        r["Decision"] = dec
        got[dec].append(r)
    for dec, fname in (("Keep", "approved.csv"), ("Drop", "rejected.csv")):
        old, _ = _read_csv(os.path.join(d, fname))
        have = {r["Lead Key"] for r in old}
        merged = old + [r for r in got[dec] if r["Lead Key"] not in have]
        _write_csv(os.path.join(d, fname), merged, fields)
    pend, _ = _read_csv(os.path.join(d, "pending.csv"))
    decided = {r["Lead Key"] for r in got["Keep"] + got["Drop"]}
    pend = [r for r in pend if r["Lead Key"] not in decided]
    have = {r["Lead Key"] for r in pend}
    pend += [r for r in got["Unsure"] if r["Lead Key"] not in have]
    _write_csv(os.path.join(d, "pending.csv"), pend, fields)
    counts = {k or "Undecided": len(v) for k, v in got.items()}
    log(name, "approve", root, file=os.path.basename(reviewed_csv), **counts)
    return counts


# ---- outreach plan ---------------------------------------------------------
def load_suppressions(name, root=ROOT):
    """suppress.csv, one value per row under a 'value' header: an email, a domain, or a company name. Opt-outs and do-not-contact go here."""
    rows, _ = _read_csv(os.path.join(folder(name, root), "suppress.csv"))
    return {norm_name(r["value"]) if "@" not in r["value"] and "." not in r["value"] else r["value"].strip().lower() for r in rows if r.get("value")}


def suppressed(row, sup):
    email = (row.get("Email") or "").strip().lower()
    return bool(sup) and (email in sup or (email and email.split("@")[-1] in sup) or norm_name(row.get("Company", "")) in sup
                          or lead_key(row).lower() in sup)


def _next_weekday(d):
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def compliance(name, spec, approved, root=ROOT):
    """Blocking problems (placeholders, missing opt-out or postal address) and non-blocking warnings."""
    cfg = config.load(os.path.join(folder(name, root), "config.json"))
    block, warn = [], []
    for k in ("name", "business", "address", "offer"):
        if PLACEHOLDER.search(str(cfg["sender"].get(k, ""))) or not str(cfg["sender"].get(k, "")).strip():
            block.append(f"config.json sender.{k} is empty or still a [placeholder]")
    if any("Draft Email 1" in r and r["Draft Email 1"] and not re.search(r"no thanks|unsubscribe|opt out|stop", r["Draft Email 1"], re.I) for r in approved):
        block.append("some drafts have no opt-out line; commercial email needs one (CAN-SPAM)")
    if any(s["channel"] == "phone" for s in spec["outreach"]["sequence"]):
        warn.append("phone steps: check the National Do-Not-Call Registry and your state's rules before calling; business lines are treated differently from mobiles")
    if "example.com" in cfg["sender"].get("portfolio_url", ""):
        warn.append("sender.portfolio_url is still the example.com placeholder")
    if cfg["sender"].get("link_mode") == "redirect":
        warn.append("link_mode 'redirect' puts a third-party domain in the email, which can hurt deliverability; 'utm' is safer")
    return block, warn


def plan_outreach(name, start, root=ROOT, force=False):
    """Approved leads -> dated tasks that respect daily caps per channel and skip weekends and suppressed contacts. Nothing is sent."""
    spec = load(name, root)
    approved, fields = _read_csv(os.path.join(folder(name, root), "approved.csv"))
    if not approved:
        raise SystemExit("No approved leads yet. Review a pack and run: leadengine campaign approve " + name + " FILE")
    block, warn = compliance(name, spec, approved, root)
    if block and not force:
        raise SystemExit("Fix before planning outreach:\n  - " + "\n  - ".join(block))
    odir = os.path.join(folder(name, root), "outreach")
    planned_path = os.path.join(odir, "planned.json")
    planned = set(_read_json(planned_path)) if os.path.exists(planned_path) else set()
    approved = [r for r in approved if r["Lead Key"] not in planned]
    if not approved:
        raise SystemExit("Every approved lead is already in an outreach plan. Approve more leads first.")
    sup = load_suppressions(name, root)
    caps, seq = spec["outreach"]["daily_caps"], spec["outreach"]["sequence"]
    load_ = {}
    for f in (sorted(os.listdir(odir)) if os.path.isdir(odir) else []):        # earlier plans already use up daily capacity
        if f.startswith("tasks-"):
            for t in _read_csv(os.path.join(odir, f))[0]:
                k = (dt.date.fromisoformat(t["Date"]), t["Channel"])
                load_[k] = load_.get(k, 0) + 1
    tasks, skipped = [], []

    def slot(day, ch):
        day = _next_weekday(day)
        while load_.get((day, ch), 0) >= caps[ch]:
            day = _next_weekday(day + dt.timedelta(days=1))
        load_[(day, ch)] = load_.get((day, ch), 0) + 1
        return day

    def reachable(row, ch):
        return {"email": (row.get("Email") or "").strip() and (row.get("Email Status") or "").strip().lower() not in ("invalid", "bounced"),
                "phone": (row.get("Phone") or "").strip(), "linkedin": (row.get("LinkedIn URL") or "").strip()}[ch]

    for row in approved:
        if suppressed(row, sup):
            skipped.append((row["Company"], "suppressed"))
            continue
        base = start
        for i, st in enumerate(seq, 1):
            ch = st["channel"]
            if not reachable(row, ch):
                skipped.append((row["Company"], f"step {i} ({ch}): no usable contact"))
                continue
            target = base + dt.timedelta(days=st["day"])
            when = slot(target, ch)
            if when > target:                      # a full day or a weekend pushed this step: keep the later spacing
                base += when - target
            tasks.append({"Date": when.isoformat(), "Channel": ch, "Step": i, "Action": st["action"], "Company": row["Company"],
                          "Contact": " ".join(x for x in (row.get("First Name"), row.get("Last Name")) if x),
                          "Where": {"email": row.get("Email"), "phone": row.get("Phone"), "linkedin": row.get("LinkedIn URL")}[ch],
                          "Lead Key": row["Lead Key"], "Subject": row.get("Draft Subject", "") if (ch == "email" and i == 1) else "",
                          "Draft": row.get("Draft Email 1", "") if (ch == "email" and i == 1) else "",
                          "Approved to send (Y/N)": "", "Done (Y/N)": "", "Outcome / notes": ""})
    tasks.sort(key=lambda t: (t["Date"], t["Channel"], t["Company"]))
    n_prior = len([f for f in (os.listdir(odir) if os.path.isdir(odir) else []) if f.startswith("tasks-")])
    out = os.path.join(odir, f"tasks-{start.isoformat()}" + (f"-{n_prior + 1}" if n_prior else "") + ".csv")
    _write_csv(out, tasks, list(tasks[0]) if tasks else ["Date"])
    _write_json(planned_path, sorted(planned | {r["Lead Key"] for r in approved if r["Company"] not in {c for c, w in skipped if w == "suppressed"}}))
    log(name, "outreach_plan", root, start=start.isoformat(), tasks=len(tasks), skipped=len(skipped), forced=bool(block and force))
    return out, len(tasks), skipped, block, warn


# ---- status ---------------------------------------------------------------
def status(name, root=ROOT):
    spec = load(name, root)
    d = folder(name, root)
    problems = validate(spec)
    pk = _review_packs(name, root)
    delivered = sum(len(_read_csv(p)[0]) for p in pk)
    decided = {k: len(_read_csv(os.path.join(d, f))[0]) for k, f in (("kept", "approved.csv"), ("dropped", "rejected.csv"), ("unsure", "pending.csv"))}
    outs = sorted(os.listdir(os.path.join(d, "outreach"))) if os.path.isdir(os.path.join(d, "outreach")) else []
    stages = {
        "define": "done" if not problems else "blocked",
        "discover": "done" if pk else ("blocked" if problems or blockers(spec) else "ready"),
        "review": "waiting on human" if pk and (decided["kept"] + decided["dropped"] + decided["unsure"] < delivered) else ("done" if pk else "not started"),
        "outreach_plan": "done" if outs else ("ready" if decided["kept"] else "not started"),
    }
    todo = blockers(spec)
    if problems:
        nxt = "fix the spec problems"
    elif todo:
        nxt = "human: " + "; ".join(todo)
    elif not pk:
        nxt = f"agent: leadengine campaign run {name}"
    elif stages["review"] == "waiting on human":
        nxt = f"human: mark Decision in {pk[-1]} then run: leadengine campaign approve {name} <file>"
    elif not outs and decided["kept"]:
        nxt = f"agent: leadengine campaign outreach {name} --start YYYY-MM-DD (then a human approves each send)"
    else:
        nxt = f"agent: leadengine campaign run {name} for the next stage, or a human starts sending from {outs[-1] if outs else 'the task list'}"
    return {"campaign": name, "stages": stages, "review_packs": len(pk), "leads_delivered": delivered, "decisions": decided,
            "outreach_files": outs, "problems": problems, "blockers": todo, "next_action": nxt}


# ---- CLI ------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(prog="leadengine campaign", description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create campaigns/<name>/ from a vertical pack")
    p.add_argument("name")
    p.add_argument("--state", required=True)
    p.add_argument("--county", action="append", default=[])
    p.add_argument("--city", action="append", default=[], help="'City, ST' (repeatable)")
    p.add_argument("--vertical", default="healthcare-practices", help="pack id in data/verticals/")
    p.add_argument("--tier", action="append", default=None)
    sub.add_parser("list")
    for c in ("validate", "status", "run"):
        sub.add_parser(c).add_argument("name")
    sub.choices["status"].add_argument("--json", action="store_true")
    sub.choices["run"].add_argument("--target", type=int)
    p = sub.add_parser("approve", help="read a reviewed pack (Keep / Drop / Unsure)")
    p.add_argument("name")
    p.add_argument("file")
    p = sub.add_parser("outreach", help="plan dated tasks from approved leads (sends nothing)")
    p.add_argument("name")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--force", action="store_true", help="plan even if compliance checks fail (not recommended)")
    a = ap.parse_args(argv)
    root = a.root
    if a.cmd == "init":
        spec, problems = init(a.name, a.state, a.county, a.city, a.vertical, a.tier or ["focus"], root)
        print(f"Created {folder(a.name, root)}/ (spec.json, config.json). Edit config.json's sender block before outreach.")
        for x in problems:
            print("  problem:", x)
    elif a.cmd == "list":
        for n in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            if os.path.exists(os.path.join(root, n, "spec.json")):
                print(n)
    elif a.cmd == "validate":
        problems = validate(load(a.name, root))
        print("\n".join(problems) if problems else "ok")
        return 1 if problems else 0
    elif a.cmd == "status":
        st = status(a.name, root)
        if a.json:
            print(json.dumps(st, indent=2))
        else:
            print(f"Campaign {st['campaign']}: " + " | ".join(f"{k}: {v}" for k, v in st["stages"].items()))
            print(f"Packs {st['review_packs']}, leads delivered {st['leads_delivered']}, decisions {st['decisions']}")
            for x in st["problems"] + st["blockers"]:
                print("  !", x)
            print("Next:", st["next_action"])
    elif a.cmd == "run":
        for path in run_discover(a.name, root, a.target):
            print("Review pack:", path)
    elif a.cmd == "approve":
        print(approve(a.name, a.file, root))
    elif a.cmd == "outreach":
        out, n, skipped, block, warn = plan_outreach(a.name, dt.date.fromisoformat(a.start), root, a.force)
        print(f"{n} tasks -> {out}; {len(skipped)} skipped")
        for x in block + warn:
            print("  note:", x)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
