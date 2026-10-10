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

## Launch pricing (opens November 1, 2026)

Everything on this page is **introductory launch pricing**.
* **Window:** 90 days from `campaign launch <name> --start 2026-11-01`: it ends **January 30, 2027** (the last day to sign is **January 29**). The end date is stored and fixed; it does not move if settings change.
* **Lock:** the **first 100 clients** who sign inside the window keep their launch prices for **12 months from signing**. The 101st signer, or anyone signing after the window, pays regular prices.
  The tool records "Launch price = Y" and the lock end date on each qualifying deal, and `campaign status` shows the slots left.
* **What the lock covers (confirm):** the care plan prices, the add-on prices and the out-of-plan hourly rate for those 12 months. The one-time site price is simply what they pay at signing.
* **Regular prices after the launch:** still to be set (`list_price` on each product, plan and add-on). Suggestions are in `docs/PRICING_GUIDANCE.md`. Do not advertise a "was/now" or "% off" comparison until the regular price has genuinely been offered; say "regular prices apply from <date>" instead.

## Care plans (monthly; set in `offer.plans`), all fully capped

| Plan | Price | Includes | Hard limits |
|---|---|---|---|
| Basic upkeep | $9.99/mo | keeps the site online and secure | no changes at all |
| Upkeep + 1 change | $20/mo | upkeep plus one change or update a month | **30 minutes** of work; one change; no rollover |
| Priority upkeep | **$99/mo** | tier 1 support, advanced upkeep, up to 5 changes a month | **2 hours of work in total a month**; no single change over 2 hours; no rollover |

**Over the limit = separate paid work.** Any change that needs more than the plan allows is quoted in writing as a separate project, billed on top, and ownership passes to the client on payment.
You called this "work for hire"; the contract words it as separately quoted paid work, because "work made for hire" has a narrow legal meaning for copyright. Ask your attorney.

**Economics** (`python3 tools/funnel.py`): the $9.99 plan nets about $9.40 after card fees and pays only if it takes almost no time (about 11 minutes a month to break even at $50 an hour).
The $20 plan at its 30-minute limit is $40 an hour. The $99 plan at its 2-hour limit is $49.50 an hour, and better in a typical month.

## Add-ons (quoted separately; launch prices adopted, rationale in `docs/PRICING_GUIDANCE.md`)

| Add-on | Launch price |
|---|---|
| Privacy and data-retention policy: drafted from `privacy-policy-template.md`; the client's attorney must review it | $195 |
| Logo and brand basics (logo, 2 colors, 1 font, vector files, one revision round) | $350 |
| Copywriting beyond light edits, from the client's facts | $150 per page |
| Out-of-plan work: hourly, 1-hour minimum, 30-minute blocks (fixed quote for known jobs) | $85 per hour |

If a client has no privacy policy, logo, copy or imagery, quote these separately. The build does not start until the materials exist.

## Outreach is digital; calls only when required

* **No cold calling.** First contact is email and LinkedIn, aimed at your own properties (portfolio, booking link, tracker) so interest shows up as engagement. Phone is off by default (`outreach.phone_policy: on_request_only`).
* **When a call is absolutely required** (a prospect can only be reached or only agrees by phone), record it with `deal call <campaign> <deal> --reason "..."`. It is held for the **Friday 10:00-15:00** block.

## Your schedule and parallel builds

* **2 hours a night, up to 5 nights (10 hours a week), after 10pm.** Build, review and approve at night. Emails carry a send window (09:30-11:30 recipient time) so batches are scheduled, not sent at night.
* **Up to 3 sites in build at once** (`offer.max_parallel_builds`): `deal start` refuses a fourth until one is delivered. Building in parallel lets you batch setup, QA and handoff.
* **Capacity follows your hours.** At 2.5-3 hours a site that is about 2 sites a week. If batching three at a time lowers your hours per site, set `operator.parallel_efficiency` (1.5 means 1.5x faster) after you have measured it.
  If you are booked more than 2 weeks out, raise prices.

## Rules

1. **Capacity:** the lower of 10 projects a week and what your hours allow. Counted when work starts. When full, outreach pauses (`campaign status` says so). Up to 3 builds at once.
2. **Remote first.** Email, LinkedIn, video. No cold calls; a call only when required. Never a standard in-person step.
3. **In-person only when a deal is worth $5,000 a month or more** (`offer.in_person_min_monthly_value`). The pipeline report lists the deals that qualify. Under that line, do it remotely.
4. **No patient information** is collected through the sites you build, and you do not sign BAAs. Say so in the proposal.
5. **Proof:** show 2-3 examples. A medical-practice example (even a self-made demo site) beats a general portfolio.
