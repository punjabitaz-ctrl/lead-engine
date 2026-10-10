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
ap.add_argument("--plan-take", type=float, default=0.4, help="share of clients who buy any care plan (assumption)")
ap.add_argument("--plan-mix", default="9.99:0.5,20:0.35,99:0.15", help="price:share of plan buyers (assumption)")
ap.add_argument("--plan-hours", default="9.99:0.1,20:0.5,99:1.5", help="your hours a month per client on each plan (assumption)")
ap.add_argument("--fee", type=float, default=0.029, help="card fee rate; plus $0.30 per charge")
ap.add_argument("--plan-months", type=float, default=12, help="months a plan client stays (assumption)")
ap.add_argument("--delivery-hours", type=float, default=2.5, help="your hours to deliver one site (you said 2-3 with complete client inputs)")
ap.add_argument("--minutes-manual", type=float, default=21, help="your minutes per contact done by hand (review, find contact, 3-5 touches)")
ap.add_argument("--minutes-batch", type=float, default=4, help="your minutes per contact when outreach is templated and approved in batches")
ap.add_argument("--hourly", type=float, default=50)
a = ap.parse_args()

SCEN = {"low": (1.0, 0.20), "base": (3.0, 0.25), "high": (6.0, 0.35)}   # positive conversations per 100 contacted, meeting->sale close
price = a.price1 * (1 - a.share3) + a.price3 * a.share3
mix = {float(k): float(v) for k, v in (x.split(":") for x in a.plan_mix.split(","))}
hrs = {float(k): float(v) for k, v in (x.split(":") for x in a.plan_hours.split(","))}
cash = sum(share * (pr - pr * a.fee - 0.30) for pr, share in mix.items())          # per month, per plan client, after card fees
labour = sum(share * hrs[pr] for pr, share in mix.items())                         # your hours per month, per plan client
plan_net = cash - labour * a.hourly                                                # contribution per month if your hour is worth `hourly`
value = price + a.plan_take * a.plan_months * cash
contacted = a.leads * a.contactable
print(f"Care plans (per plan client, per month): cash after card fees ${cash:.2f}; your time {labour:.2f} h; net of your time at ${a.hourly:.0f}/h: ${plan_net:+.2f}.")
for pr in sorted(mix):
    net = pr - pr * a.fee - 0.30 - hrs[pr] * a.hourly
    print(f"   ${pr:>5.2f} plan: {hrs[pr]:g} h/month -> ${net:+.2f}/month after fees and your time; break-even at {max(pr - pr * a.fee - 0.30, 0) / a.hourly * 60:.0f} min of work a month")
print(f"{a.leads} leads -> {contacted:.0f} contactable. Average first sale ${price:,.0f}; first-year value per client ${value:,.0f} (sale plus a year of plan cash; support time is counted in the hours below).\n")
print(f"{'':6}{'sales':>6}{'revenue':>9}{'$/h by hand':>13}{'$/h batched':>13}   contacts per sale")
for k, (conv, close) in SCEN.items():
    sales = contacted / 100 * conv * 0.6 * close          # 60% of positive conversations become calls or meetings
    rev = sales * value
    support = sales * a.plan_take * a.plan_months * labour       # support hours over the plan's life
    h_manual = contacted * a.minutes_manual / 60 + sales * a.delivery_hours + support
    h_batch = contacted * a.minutes_batch / 60 + sales * a.delivery_hours + support
    print(f"{k:6}{sales:>6.2f}{rev:>9,.0f}{rev / h_manual:>13.0f}{rev / h_batch:>13.0f}   {100 / (conv * 0.6 * close):.0f}")
budget = max(value - (a.delivery_hours + a.plan_take * a.plan_months * labour) * a.hourly, 0) / a.hourly
print(f"\nTo earn ${a.hourly}/h you can spend {budget:.1f} hours of outreach per sale in total. At the base case that is "
      f"{budget * 60 / (100 / (3.0 * 0.6 * 0.25)):.1f} minutes per contact.")
