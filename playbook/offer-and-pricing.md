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

## Care plans (monthly; set in `offer.plans`) — all fully capped

| Plan | Price | Includes | Hard limits |
|---|---|---|---|
| Basic upkeep | $9.99/mo | keeps the site online and secure | no changes at all |
| Upkeep + 1 change | $20/mo | upkeep plus one change or update a month | **30 minutes** of work; one change; no rollover |
| Priority upkeep | $50/mo | tier 1 support, advanced upkeep, up to 5 code changes a month | each change up to **190 minutes**; **4 hours of work in total a month**; no rollover |

**Over the limit = separate paid work.** Any change that needs more than the plan allows (for example more than 30 minutes on the $20 plan, or more than 190 minutes
or 4 hours a month on the $50 plan) is quoted in writing as a separate project, billed on top, and ownership passes to the client on payment. This is what you called
"work for hire"; in the contract it is written as separately quoted paid work, because "work made for hire" has a narrow legal meaning for copyright. Ask your attorney.

**Check the economics** (`python3 tools/funnel.py`, `campaign status` warnings):
* The $9.99 plan nets about $9.40 after card fees; it pays only if it takes almost no time (about 11 minutes a month to break even at $50 an hour).
* The $20 plan with a 30-minute limit is $40 an hour at the limit, below a $50 target but workable.
* The $50 plan even capped at 4 hours is $12.50 an hour at the limit. To be $50 an hour at the limit it would need to be $200 a month, or capped at 60 minutes.

## Add-ons (quoted separately; prices TBD, guidance in `docs/PRICING_GUIDANCE.md`)

| Add-on | Suggested starting price (to test) |
|---|---|
| Privacy and data-retention policy: drafted from `privacy-policy-template.md`; the client's attorney must review it | $195 |
| Logo and brand basics (logo, 2 colors, 1 font, vector files, one revision round) | $350 |
| Copywriting beyond light edits, from the client's facts | $150 per page |
| Out-of-plan work: hourly, 1-hour minimum, 30-minute blocks (fixed quote for known jobs) | $85 per hour |

If a client has no privacy policy, logo, copy or imagery, quote these separately. The build does not start until the materials exist.

## Your schedule (2 hours a night, up to 5 nights, after 10pm; Fridays 10am-3pm for calls)

* **Build, review and approve at night.** **Send during the recipient's business hours:** the tool exports a send window (09:30-11:30 by default) so batches are scheduled, not sent at night.
* **Calls happen Fridays 10:00-15:00** (`outreach.call_window`, covered by `operator.daytime_blocks`). Phone steps are only scheduled on Fridays, at most 10 a day.
* **Capacity follows your hours.** 10 hours a week, 40% to outreach, 2.5-3 hours a site is about **2 sites a week** (`campaign status` shows `effective_capacity`). If you are booked past two weeks, raise prices.

## Rules

1. **Capacity: 10 projects a week at most** (`offer.capacity_per_week`), or fewer if your hours allow (`operator.hours_per_week`). Counted when work starts. When full, outreach pauses (`campaign status` says so).
2. **Remote first.** Email, phone, video. Never a standard in-person step.
3. **In-person only when a deal is worth $5,000 a month or more** (`offer.in_person_min_monthly_value`). The pipeline report lists the deals that qualify. Under that line, do it remotely.
4. **No patient information** is collected through the sites you build, and you do not sign BAAs. Say so in the proposal.
5. **Proof:** show 2-3 examples. A medical-practice example (even a self-made demo site) beats a general portfolio.
