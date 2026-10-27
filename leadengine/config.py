"""Defaults mirror the Config tab of lead-engine-template.xlsx. Sender details are placeholders on purpose: set them in
campaigns/<name>/config.json (or --config path/to/file.json); campaign outreach planning refuses to run until they are filled in."""
import copy
import json

DEFAULTS = {
    "sender": {
        "name": "[Your name]",
        "business": "[Your business name]",
        "address": "[Street, City, State ZIP]",
        "portfolio_url": "https://example.com/portfolio",
        "booking_link": "",
        "reply_email": "",
        "tracker_base": "",
        "link_mode": "utm",
        "offer": "[One sentence: what you do and how fast]",
    },
    "target": {"employees_min": 20, "employees_max": 250},
    "points": {
        "vertical": 10, "size": 10, "metro": 10, "hiring": 15, "psi_poor": 10, "psi_moderate": 5,
        "outdated": 8, "expansion": 7, "no_website": 20, "no_gbp": 12, "thin_profile": 5, "email_valid": 10, "email_risky": 5, "phone": 5, "linkedin": 5,
        "fresh1": 10, "fresh2": 5,
    },
    "thresholds": {"urgency_cap": 40, "thin_reviews": 10, "psi_poor": 50, "psi_moderate": 75, "fresh1_days": 30, "fresh2_days": 90,
                   "grade_a": 75, "grade_b": 60, "grade_c": 40},
    "signal": {"hot_days": 30, "warm_days": 90, "hot_min_postings": 2},
    "size": {"basis": "clinicians", "small_max": 5, "medium_max": 15},
    "mail": {
        "provider": "smtp",                 # smtp | gmail | file (dry run); see docs/EMAIL_SENDING.md
        "from_email": "",                   # the address you send from: the account you log in with
        "unsubscribe_email": "",            # where opt-outs go (default: sender.reply_email, then from_email)
        "unsubscribe_url": "",              # optional https page that unsubscribes in one click
        "ad_disclosure": True,              # footer says plainly that it is a marketing email
        "batch_size": 10,
        "daily_cap": 30,                    # per sending address, across every campaign
        "warmup": [[7, 10], [14, 20]],      # a new address: 10 a day in week 1, 20 in week 2, then daily_cap
        "delay_seconds": [60, 180],         # random pause between emails
        "max_failures": 3,                  # stop the batch after this many failures
        "bounce_limit": 0.05,               # stop sending when over 5% of the last 30 days' emails bounced
        "min_days_between": 30,             # no marketing email to the same address more often than this
        "allowed_email_status": ["Valid", "Risky"],
        "one_per_domain": True,             # one person per business domain in a mailing (free mail like gmail.com is not grouped)
        "timezone": "",                     # recipients' time zone for the send window (default: the spec's operator timezone)
    },
    "exclude_large": False,
    "excluded_job_types": ["part-time", "internship"],
}


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load(path=None, pack=None):
    """Defaults, then the vertical pack's own "config" block (sizing, points, targets that suit that market), then the file."""
    cfg = copy.deepcopy(DEFAULTS)
    if pack and pack.get("config"):
        _merge(cfg, copy.deepcopy(pack["config"]))
    if path:
        with open(path, encoding="utf-8") as fh:
            _merge(cfg, json.load(fh))
    return cfg
