# Offer and pricing

## Products (set in the campaign's `spec.json`, `offer.products`)

| ID | Product | Price | Included |
|---|---|---|---|
| `page1` | Single-page site | $250 | one mobile-friendly page: practice name, services, location and map, hours, phone, contact form (no patient details), Google Business Profile link |
| `page3` | 3-page basic site | $500 | home, services, about/contact, same extras, a basic privacy notice |

**The 72-hour clock** starts only when (1) the agreement is signed, (2) payment is received as below, and (3) the client's intake is **complete**.
Delivery takes about 2-3 hours of your time when the client supplies everything up front, so the intake is a hard gate, not a courtesy.

**Required from the client before work starts** (`offer.intake_required`): logo and branding, imagery, text copy, videos (if any), legal or other business
data, and the privacy and data-retention policy. `leadengine campaign deal start` refuses until payment and intake are both recorded.

**Not included** (offered separately, priced when asked): logo or brand design, copywriting beyond light edits, photography, online booking, patient portals,
e-commerce, forms that collect health information, more than one round of revisions on the initial build.

## Payment before work

| Product | Payment | Work starts when |
|---|---|---|
| Single-page site, $250 | paid in full | $250 received and intake complete |
| 3-page site, $500 | 50% deposit ($250), balance at launch | $250 received and intake complete; **no deposit, no work** |

Record with `deal pay <campaign> <deal> <amount>`, then `deal intake`, then `deal start`.

## Care plans (monthly; set in `offer.plans`)

| Plan | Price | Includes | Does not include |
|---|---|---|---|
| Basic upkeep | $9.99/mo | keeps the site online and secure | any changes |
| Upkeep + 1 change | $20/mo | upkeep, plus one change or update a month | more than one change; unused change does not roll over |
| Priority upkeep | $50/mo | tier 1 support, advanced upkeep to keep the site online, up to 5 code changes a month, each needing no more than 190 minutes of work | changes over 190 minutes (quoted separately); unused changes do not roll over |

**Check the economics before launch** (`python3 tools/funnel.py` shows them, with assumptions you can change):
* After a 2.9% + $0.30 card fee the $9.99 plan nets about $9.40. It is only worth selling if it needs almost no time (break-even is about 11 minutes of work a month at a $50 hour).
* The $20 plan breaks even at about 23 minutes of work a month. Set a time limit per change (for example 30 minutes) so one change does not eat the month.
* The $50 plan's worst case is 5 changes x 190 minutes = 15.8 hours a month, about $3 an hour. Consider a monthly hours cap (for example 4 hours), no rollover, and a fair-use clause. `campaign status` prints this warning.

## Rules

1. **Capacity: 10 projects a week at most** (`offer.capacity_per_week`), counted when work starts. At 10, outreach pauses (`campaign status` says so).
2. **Remote first.** Email, phone, video. Never a standard in-person step.
3. **In-person only when a deal is worth $5,000 a month or more** (`offer.in_person_min_monthly_value`). The pipeline report lists the deals that qualify. Under that line, do it remotely.
4. **No patient information** is collected through the sites you build, and you do not sign BAAs. Say so in the proposal.
5. **Proof:** show 2-3 examples. A medical-practice example (even a self-made demo site) beats a general portfolio.
