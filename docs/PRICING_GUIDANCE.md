# Pricing guidance (draft, 2026-10-10)

The suggested add-on prices below were adopted as **introductory launch prices** on 2026-10-10 (first 90 days; list prices after the launch are still to be set). This page gives the market ranges they come from. Market figures are from vendor
and marketing pages, which have a stake in the answer and disagree with each other; treat them as rough. The add-on prices are set in `offer.add_ons[].price`.

## How to set a price

1. **Floor:** what the work costs you. Your target is $50 an hour; card fees take 2.9% + $0.30.
2. **Ceiling:** what it is worth to a practice. One new patient is typically worth far more than a $250 site, so the web price is not what limits you.
3. **Market:** what others charge (below). You can sit under agencies and above template sites.
4. **Simplicity:** few options, fixed prices where the scope is known, an hourly rate only for the unknown.

## Market ranges found

| Item | Range | Source |
|---|---|---|
| Website care plans, small business | $50-$500/month typical; $30-$250 in a narrower guide; $100-$300 from a freelancer marketplace; entry tier ~$49 | [Ueni](https://ueni.com/blog/website-maintenance-cost/), [WebsiteSetup](https://websitesetup.org/website-maintenance-costs), [Seahawk Media](https://seahawkmedia.com/?p=413926) |
| Freelance web developer, US | $50-$100/h mid-level (several sources); $85-$135/h in another; senior $95-$160/h | [SecondTalent](https://www.secondtalent.com/cost-to-hire/united-states/), [Arc](https://arc.dev/employer-blog/freelance-developers-cost/), [SoloHourly](https://solohourly.com/rates/web-developer-rates-in-united-states) |
| Simple small-business logo | $200-$800; $300-$2,000 for a professional logo; $25-$300 on budget marketplaces | [ManyPixels](https://www.manypixels.co/blog/brand-design/logo-design-cost-guide), [Made Good](https://madegooddesigns.com/how-much-does-a-logo-cost/) |
| Privacy policy and terms by an attorney | about $1,130 average to draft, about $770 to review; $500-$1,500 for a simple site | [ContractsCounsel](https://www.contractscounsel.com/b/website-terms-of-service-and-privacy-policy-drafting-cost) |
| Template or generator first, lawyer second | cheaper middle path; no law requires a lawyer to write the policy | [Termly](https://termly.io/resources/articles/do-i-need-a-lawyer-for-a-privacy-policy) |
| Website copy, per page | $150-$500; up to $1,000 for a simple page in another guide; $50-$150/h professionals | [Sidestackers](https://www.sidestackers.com/blog/copywriter-rates), [NewMedia](https://newmedia.com/blog/copywriting-rates) |

The $250/$500 site prices were not benchmarked here. Your care plans ($9.99-$50) are well below the typical small-business range ($50-$500+), which is fine for a door-opener
and means there is room to raise them once you are busy.

## Suggested starting prices (to test)

| Add-on | Suggest | Why |
|---|---|---|
| Out-of-plan work | **$85/hour**, 1-hour minimum, billed in 30-minute blocks; fixed quote for known jobs (for example add a page: $150) | mid-level market is $50-$100 an hour; ad-hoc requests interrupt your late-night blocks, so price above your $50 target. The minimum stops 10-minute favors. |
| Privacy and data-retention policy | **$195** for a draft from the template, filled in for their practice; they pay their attorney separately (market review about $770) | about 2 hours of your time including a client call; far below drafting by an attorney ($1,130 average), and positioned as "draft for your attorney", not legal advice. |
| Logo and brand basics | **$350**: logo, two colors, one font, vector files and commercial rights, one revision round | simple-logo market $200-$800; about 5 hours at about $70 an hour. Confirm in writing that they receive source files and full rights. |
| Copywriting beyond light edits | **$150 per page**, from the client's facts and approval | bottom of the $150-$500 per-page market because you write from supplied facts; raise if you start interviewing and researching. |

## The top care plan (decided: option B, $99 with a 2-hour cap)

At its earlier terms the $50 plan could cost you 4 hours for $50 ($12.50 an hour at the limit). Options considered (B chosen on 2026-10-10):

| Option | Price | Cap | Worst case per hour |
|---|---|---|---|
| A. Cap the time | $50 | 1 hour of work a month | $50 |
| B. Raise price, cap at 2 hours | $99 | 2 hours | $49.50 |
| C. Keep a big cap, price to match | $200 | 4 hours | $50 |
| D. Keep as is | $50 | 4 hours | $12.50 |

Most months a client will use far less than the cap, so the typical hourly rate is better than the worst case. Still, A or B keeps the tier honest. B puts the plan at the low end of
the $50-$500 market, where its "tier 1 support" claim is more credible.

## Suggested regular (list) prices for after the launch

Still to be decided by you; these are starting points (stored as `suggested_list_price`, not used). More market data found for this: a 5-page small-business site from a freelancer is mostly
**$1,500-$5,000** ([PlayCode](https://playcode.io/blog/how-much-does-a-website-cost), [Seahawk Media](https://seahawkmedia.com/tech/small-business-website-costs/)); budget freelancers go as low as
$299-$499 with inconsistent quality; template or DIY tiers for a practice run **$0-$1,000** ([Project Cost Estimator](https://projectcostestimator.com/blog/dental-practice-website-cost-2026)).
Both prices are far below the freelancer market, so there is room to roughly double after the launch.

| Item | Launch | Suggested regular | Reasoning |
|---|---|---|---|
| One-page site | $250 | $500 | top of the budget-freelancer band; still under the $1,000 template-tier ceiling |
| Three-page site | $500 | $1,000 | half the $1,500 freelancer floor for 5 pages; fixed scope and 72-hour delivery justify it |
| Basic upkeep | $9.99 | $19 | still under the $30-$50 low end of care plans, and card fees matter at this size |
| Upkeep + 1 change | $20 | $39 | one 30-minute change is worth about $55 at $110 an hour |
| Priority upkeep | $99 | $149 | the cap is 2 hours; $149 is $74.50 an hour at the limit and below the $100-$300 typical plan |
| Privacy policy draft | $195 | $295 | about 2 hours; far below attorney drafting (about $1,130) |
| Logo and brand basics | $350 | $495 | within the $200-$800 simple-logo range |
| Copywriting | $150/page | $200/page | bottom of the $150-$500 market |
| Out-of-plan work | $85/h | $110/h | upper-middle of the $50-$100+ freelancer band |

Notes: roughly 1.5x to 2x the launch price keeps the step visible without sticker shock. A launch price below the market can signal low quality, so the page frames it as introductory with a fixed end date
and a real cap. Do not use "was/now" or "% off" wording until the higher price has genuinely been offered.

## Rules of thumb

* **Publish a one-page price card** and quote from it. Do not negotiate on the first call; remove scope instead of discounting.
* **If you are booked more than 2 weeks out, raise prices about 20%.** At 2 sites a week (10 hours), demand above that is the signal.
* **Review after 10 sales:** how many took a plan, which plan, how much support each used. Change prices from that data, not from this page.
* **Every out-of-plan job gets a written quote before work.** No quote, no work.
