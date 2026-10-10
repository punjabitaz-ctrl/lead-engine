"""Back-of-envelope funnel: do the leads pay for the time? Every default below is an ASSUMPTION, not a measured result.
Replace them with your price, your delivery hours and, after the first sprint, your real rates.

  python3 tools/funnel.py                        # low / base / high
  python3 tools/funnel.py --price 4500 --leads 250
"""
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("--leads", type=int, default=250, help="leads delivered")
ap.add_argument("--contactable", type=float, default=0.5, help="share with a usable email or phone after enrichment")
ap.add_argument("--price", type=float, default=3000, help="first project price")
ap.add_argument("--retainer", type=float, default=300, help="monthly retainer (local search, updates)")
ap.add_argument("--retainer-take", type=float, default=0.4, help="share of clients who take the retainer")
ap.add_argument("--retainer-months", type=float, default=12)
ap.add_argument("--delivery-hours", type=float, default=15, help="your hours to deliver one site")
ap.add_argument("--hours-per-100", type=float, default=35, help="your hours per 100 contacts: reviewing, finding contacts, 3-5 touches, calls")
ap.add_argument("--hourly", type=float, default=50, help="what an hour of your time is worth")
a = ap.parse_args()

SCEN = {  # positive conversations per 100 contacted, meeting->sale close rate
    "low": (1.0, 0.20),
    "base": (3.0, 0.25),
    "high": (6.0, 0.35),
}
contacted = a.leads * a.contactable
print(f"{a.leads} leads -> {contacted:.0f} contactable. Price ${a.price:,.0f}, retainer ${a.retainer:,.0f}/mo x {a.retainer_take:.0%} take x {a.retainer_months:.0f} mo. ASSUMPTIONS.\n")
print(f"{'':6}{'sales':>7}{'first-year revenue':>20}{'your hours':>12}{'$/hour':>9}   leads needed for 1 sale")
for k, (conv, close) in SCEN.items():
    sales = contacted / 100 * conv * 0.6 * close          # 60% of positive conversations become meetings
    rev = sales * (a.price + a.retainer * a.retainer_take * a.retainer_months)
    hours = contacted / 100 * a.hours_per_100 + sales * a.delivery_hours
    per_sale_contacts = 100 / (conv * 0.6 * close)
    print(f"{k:6}{sales:>7.2f}{rev:>20,.0f}{hours:>12.0f}{rev / hours:>9.0f}   {per_sale_contacts:.0f} contacts (~{per_sale_contacts / a.contactable:.0f} leads)")
print(f"\nBreak-even against your time at ${a.hourly}/h needs more than ${a.hourly}/h in the $/hour column.")
