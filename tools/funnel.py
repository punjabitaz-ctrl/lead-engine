"""Back-of-envelope funnel: do the leads pay for the time? Every default is an ASSUMPTION except the two prices, which are the seller's.
Replace the rest with measured numbers after the first sprint.

  python3 tools/funnel.py                         # low / base / high
  python3 tools/funnel.py --retainer 99 --retainer-take 0.3
"""
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("--leads", type=int, default=250, help="leads delivered")
ap.add_argument("--contactable", type=float, default=0.5, help="share with a usable email or phone after enrichment")
ap.add_argument("--price1", type=float, default=250, help="single-page site")
ap.add_argument("--price3", type=float, default=500, help="3-page site")
ap.add_argument("--share3", type=float, default=0.4, help="share of buyers who take the 3-page site")
ap.add_argument("--retainer", type=float, default=0, help="monthly retainer; unknown today, so zero")
ap.add_argument("--retainer-take", type=float, default=0.0)
ap.add_argument("--retainer-months", type=float, default=12)
ap.add_argument("--delivery-hours", type=float, default=3, help="your hours to deliver one site (assumption: template-based)")
ap.add_argument("--minutes-manual", type=float, default=21, help="your minutes per contact done by hand (review, find contact, 3-5 touches)")
ap.add_argument("--minutes-batch", type=float, default=4, help="your minutes per contact when outreach is templated and approved in batches")
ap.add_argument("--hourly", type=float, default=50)
a = ap.parse_args()

SCEN = {"low": (1.0, 0.20), "base": (3.0, 0.25), "high": (6.0, 0.35)}   # positive conversations per 100 contacted, meeting->sale close
price = a.price1 * (1 - a.share3) + a.price3 * a.share3
value = price + a.retainer * a.retainer_take * a.retainer_months
contacted = a.leads * a.contactable
print(f"{a.leads} leads -> {contacted:.0f} contactable. Average first sale ${price:,.0f}; first-year value per client ${value:,.0f}.\n")
print(f"{'':6}{'sales':>6}{'revenue':>9}{'$/h by hand':>13}{'$/h batched':>13}   contacts per sale")
for k, (conv, close) in SCEN.items():
    sales = contacted / 100 * conv * 0.6 * close          # 60% of positive conversations become calls or meetings
    rev = sales * value
    h_manual = contacted * a.minutes_manual / 60 + sales * a.delivery_hours
    h_batch = contacted * a.minutes_batch / 60 + sales * a.delivery_hours
    print(f"{k:6}{sales:>6.2f}{rev:>9,.0f}{rev / h_manual:>13.0f}{rev / h_batch:>13.0f}   {100 / (conv * 0.6 * close):.0f}")
budget = max(value - a.delivery_hours * a.hourly, 0) / a.hourly
print(f"\nTo earn ${a.hourly}/h you can spend {budget:.1f} hours of outreach per sale in total. At the base case that is "
      f"{budget * 60 / (100 / (3.0 * 0.6 * 0.25)):.1f} minutes per contact.")
