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
    "size": {"small_max": 5, "medium_max": 15},
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


def load(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path, encoding="utf-8") as fh:
            _merge(cfg, json.load(fh))
    return cfg
