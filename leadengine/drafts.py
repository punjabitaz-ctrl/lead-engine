"""Email 1 drafts, same tokens as the Templates tab. Drafts are text only; nothing is ever sent."""
import json
import os

from .keys import dedupe_key, tracked_link
from .scoring import primary_signal

with open(os.path.join(os.path.dirname(__file__), "data", "templates.json"), encoding="utf-8") as _fh:
    T = json.load(_fh)


def _fill(text, vals):
    for k, v in vals.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def draft(lead, cfg):
    s = cfg["sender"]
    sig = primary_signal(lead, cfg)
    psi = lead.get("psi")
    site_issue = (f"Google's PageSpeed test scores it {psi}/100 on mobile" if isinstance(psi, (int, float))
                  else lead.get("audit_note") and f"it shows {lead['audit_note']}" or lead.get("detail") or "it looks dated on mobile")
    vals = {"company": lead["company"], "website": lead.get("website", ""), "city": lead.get("city", ""),
            "signal_detail": lead.get("detail") or "a digital role", "site_issue": site_issue}
    line = _fill(T["signals"][sig]["line"], vals)
    booking = f"\nBook directly: {s['booking_link']}" if s.get("booking_link") else ""
    body = _fill(T["body"], {"first_name": lead.get("first") or "there", "signal_line": line, "offer_line": s["offer"],
                             "portfolio_url": tracked_link(s.get("tracker_base", ""), dedupe_key(lead.get("website", ""), lead["company"], lead.get("city", "")), s["portfolio_url"], s.get("link_mode", "plain")), "booking_link": booking, "sender_name": s["name"],
                             "business_name": s["business"], "postal_address": s["address"], "company": lead["company"]})
    return sig, _fill(T["signals"][sig]["subject"], vals), body
