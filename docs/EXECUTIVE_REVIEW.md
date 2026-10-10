# Executive review: is this worth the time?

Reviewed 2026-10-10 from three seats: VP Business Development (will it produce customers), VP Technology (will it hold up), CEO (is the return worth
the hours and the opportunity cost). Basis: everything built so far on `dev/generalized-engine`, plus the private lists. Numbers marked *assumption* are
not measured; `tools/funnel.py` lets you replace them.

## Verdict

**Not yet worth continuing as built. Worth one tightly bounded test.** The system is good at the front of the funnel (list, score, draft, review gate)
and has nothing yet for the back (contact, conversation, proposal, close, measure). No message has been sent, no reply received, no sale made.
The next hours should go to proving one sale is possible, not to more lists, more counties or more modules.

## What exists, honestly

| Stage | What we have | State | Score |
|---|---|---|---|
| Generate | NPPES/Places/Adzuna adapters; 264 hand-compiled NJ practices (Middlesex, Somerset) from directory listings | adapters never run live; lists unverified, some possibly closed or system-owned | 4/10 |
| Qualify | 100-point score, size classes, ownership flags, review checklists | weights are guesses; "no website / thin profile" is a weak reason to buy; nothing validated against real buyers | 4/10 |
| Sort | grade, signal strength, specialty grouping, Size filter, review priority | works and is tested | 7/10 |
| Reach | drafts, Gmail-draft helper, tracked links, outreach planner with caps and opt-outs | no emails or owner names on any lead; sending domain not set up or warmed; tracker not live | 3/10 |
| Close | none (no CRM stages, proposal, pricing, contract, payment, onboarding) | gap | 1/10 |
| Measure | Events tab and tracker design, audit log | no data; no conversion tracking by source or signal | 2/10 |

## VP Business Development

1. **The ICP is a guess.** "Private practice with a thin web presence" says they could use help, not that they will pay or that anyone with authority is
   reachable. Most NPI-registered practices already have some site. The real buyer is an owner or office manager behind a front desk.
2. **Weak triggers.** A dated site is a constant, not an event. Events that make a practice buy now: a new practice or new location, a new provider joining,
   a move, a rebrand, rising complaints about access. NPPES records an enumeration date, so "new NPI in the last 12 months" is a cheap, strong trigger
   that we do not use yet (field believed present in API v2.1; confirm on the first live run). New practices need a site this month.
3. **Channel fit.** Cold email to medical offices is low-yield (filters, gatekeepers). For local practices a phone call, a walk-in, a LinkedIn note to the
   owner, or a referral from an adjacent vendor (EHR consultants, billing companies, dental suppliers) usually beats email. The planner already mixes
   channels; the data to support them (direct lines, owner names) is missing.
4. **The offer carries more weight than the list.** "A website in 72 hours" is a good hook, but it needs: a fixed price, a medical-practice proof piece
   (the current portfolio is not medical), and a free homepage mock-up for the top leads, which converts far better than a description.
5. **Recurring revenue is the business.** A one-off site is a small sale. The money is in monthly local search, review management and updates. The
   pitch and the pricing should start there.
6. **Close path is missing.** Minimum viable: 15-minute call script, one-page proposal, e-signature, Stripe invoice, intake form, 72-hour delivery checklist.

## VP Technology

*Strengths:* deterministic scoring with sheet/Python parity tests, resumable file-based state, a human gate that cannot be skipped, an audit log,
32 passing tests, cost caps on Places lookups, no secrets in the repo.

*Risks, in order:*
1. **Data quality is the product and it is unproven.** Every live source is "not tested live"; the lists come from web search snippets (one NPI record dates
   from 2012). Garbage in means a fast pipeline for the wrong people.
2. **Two implementations of the logic** (Sheet formulas and Python) double the maintenance and the places a change can drift. Pick the Python engine as
   the source of truth and make the Sheet a view, or drop the Sheet once the CLI is proven.
3. **Too many moving parts for one operator:** CLI, 18k-formula workbook, Apps Script, Supabase function, DNS and mailbox setup. Buy where it is cheaper than
   building: a CRM (HubSpot free or a plain Sheet pipeline), an email verifier, a sending tool.
4. **No contact enrichment**, the step that decides whether any outreach happens.
5. **Licensing is a stretch.** Apollo, Clay, Instantly and others cover generic lead tools. A licensable edge would be a vertical playbook with
   results behind it (for example "practice website sales in NJ, with conversion numbers"), not the engine itself.
6. **Compliance and deliverability:** a new sending domain needs 2-4 weeks of warm-up and 20 sends a day or fewer; the medical offer touches HIPAA
   questions (contact forms and chat on practice sites) that you should have a one-paragraph answer for.

## CEO

*Constraints on the table:* $100 budget, 2 hours a day, and a parallel search for a full-time role. Opportunity cost is real: every hour here is an
hour not spent on interviews and networking.

*What the numbers say* (`python3 tools/funnel.py`, all *assumptions*: 250 leads, 50% contactable, $3,000 project, $300/month retainer taken by 40% of clients,
35 of your hours per 100 contacts, 15 hours to deliver a site):

| Scenario | Sales from 250 leads | First-year revenue | Your hours | Revenue per hour |
|---|---|---|---|---|
| Low (1 conversation per 100 contacted) | 0.15 | $666 | 46 | $14 |
| Base (3 per 100) | 0.56 | $2,498 | 52 | $48 |
| High (6 per 100) | 1.57 | $6,993 | 67 | $104 |

Reading: on a $3,000 job the base case is roughly break-even against a $50 hour and takes about 440 leads for the first sale. At $6,000 plus a $500
retainer the base case is about $91 an hour. **Price and recurring revenue matter more than list size.** Doubling the list does not rescue a low
conversion rate; doubling conversion or price does.

*Where the value is regardless of the sale:* a working, documented, human-gated outreach system with a measured result is a strong portfolio
piece for the partnerships and business-development roles you are pursuing (what you built, the funnel numbers, what you learned). That has value
even if no practice buys. Treat it as a second reason to run the test, not as the reason to keep building.

## Update 2026-10-10: real prices change the answer

Your offer is **$250 for a single page and $500 for three pages**, up to **10 projects a week**, remote first, in person only for deals of $5,000 a month or more.
The tables above assumed a $3,000 project and no longer apply. With the real prices (`python3 tools/funnel.py`; average sale $350; every other number still an assumption):

| Scenario | Sales from 250 leads | Revenue | Revenue per hour, done by hand | Revenue per hour, batched outreach |
|---|---|---|---|---|
| Low | 0.15 | $53 | $1 | $6 |
| Base | 0.56 | $197 | $4 | $20 |
| High | 1.57 | $551 | $11 | $42 |

* **A one-off $250-$500 site cannot pay for hand-worked outreach.** To earn $50 an hour you could spend about 1 minute per contact. Calling and
  personalising each practice is out; templated outreach approved in batches is the only version that comes close, and only in the high case.
* **The monthly plan decides it.** Adding a $99 plan taken by 40% of clients lifts base-case revenue to about $464 and batched revenue per hour to about $46.
  Price and take-rate of the recurring plan matter more than list size or channel.
* **10 projects a week is not the constraint.** At about 220 contacts per sale in the base case, 10 sales a week would need over 2,000 contacts a week.
  One or two sales a week is a realistic first target; pause outreach at 10 (the pipeline does this).
* **The $250 site is a door-opener, not the business.** Use it to get a practice as a client, then sell the monthly plan, local search work and, for larger
  groups, bigger projects. In-person visits stay reserved for contracts of $5,000 a month or more, which will not come from the $250 product.

Revised sprint: same 14 days and 30 prospects, but measure *minutes per contact* and *replies per 100 contacts* as well as conversations, and test one
monthly plan price with every prospect who talks to you. Continue if you reach a projected $50 an hour including the plan; otherwise change the offer
(for example a bigger first product aimed at multi-provider practices) before changing the list.

## Update 2026-10-10 (2): care plans, payment rules and delivery time

Confirmed: care plans of **$9.99** (upkeep, no changes), **$20** (upkeep + 1 change a month) and **$50** (tier 1 support, advanced upkeep, up to 5 code changes a month of
up to 190 minutes each); a single page is paid in full before work, a 3-page site needs a 50% deposit or nothing starts; delivery takes **2-3 hours** when the client
supplies everything up front (logo, branding, imagery, copy, videos, legal or business data, privacy and data-retention policy).

Re-run with these (`python3 tools/funnel.py`; sales mix 60/40, 40% of clients buy a plan, 50/35/15 split across the plans, a year of plan life, card fees 2.9% + $0.30;
the support hours per plan per month are my assumptions: 0.1, 0.75 and 3):

| Scenario | Sales from 250 leads | Revenue (sale + year of plan cash) | Per hour, by hand | Per hour, templated outreach |
|---|---|---|---|---|
| Low | 0.15 | $66 | $1 | $7 |
| Base | 0.56 | $247 | $5 | $21 |
| High | 1.57 | $692 | $13 | $38 |

What the plans do to the case:
* **The $9.99 plan is fine only if it takes almost no time.** It nets about $9.40 after card fees; break-even against a $50 hour is about 11 minutes of work a month.
* **The $20 plan breaks even at about 23 minutes a month,** so the single included change needs a time limit (for example 30 minutes).
* **The $50 plan has an open-ended worst case:** 5 changes x 190 minutes = 15.8 hours for $50, about $3 an hour. Even at 3 hours a month it loses about $100 a month against a $50 hour.
  This is the largest hole in the offer. Options: a monthly hours cap (e.g. 4 hours), no rollover, a fair-use clause, or a higher price. `campaign status` flags it.
* **The plans do not rescue the economics at this volume.** Their job is retention and a path to bigger work. A client on the $50 plan is a sign to quote a
  larger project, not a profit centre.
* **Requiring complete materials before starting is the right call.** It is what keeps delivery at 2-3 hours. Expect friction: many practices do not have a privacy
  policy or branding ready. Decide whether you refer them elsewhere, quote that work, or lose the sale.
* **Cash-flow rules are sound:** full payment up front on $250, 50% deposit on $500. `deal start` enforces them.

Net: the offer works as a door-opener and a low-touch product *if* outreach is templated (about 4 minutes per contact or less) and you cap what each plan can consume.
At current prices it will not pay for hand-worked prospecting.

## Update 2026-10-10 (3): caps, schedule and capacity

Decisions: the $50 plan is fully capped (5 changes, 190 minutes each, **4 hours in total a month**, no rollover); the $20 plan's one change is limited to **30 minutes**;
anything over a plan's limit is quoted as separate paid work; clients without a privacy policy, logo or copy get a separate quote and the build waits for the materials; work
happens **after 10pm**.

* **Even capped, the $50 plan is $12.50 an hour at its limit.** To be $50 an hour at the limit it needs to be $200 a month, or capped at 60 minutes. Whether to hold the
  price for the sake of the $50 tier as a stepping stone is a business call; the tool keeps flagging it.
* **Late nights change capacity.** At 2.5-3 hours a site, 10 hours a week with 40% spent on outreach delivers about 2 sites a week, not 10. Set `operator.hours_per_week`.
* **Calls and nights do not mix.** Practices answer in business hours. Either reserve a daytime block, or run the sprint on email and LinkedIn, which suits evenings,
  with sends scheduled for 09:30-11:30 recipient time.
* **A privacy-policy add-on is both a sale and a risk.** Drafting from a template for the client's attorney to review is reasonable; do not present it as legal advice.

## Update 2026-10-10 (4): confirmed hours

Hours: **2 a night, up to 5 nights a week (10 hours)**, with **Fridays 10am-3pm** for calls. Capacity is therefore about **2 sites a week**, not 10: at the base case's roughly 220 contacts
per sale, even 2 sales a week needs about 440 contacts a week, which is far more than 10 hours of hand work can reach. Outreach must be templated and batch-approved, with calls
reserved for warm replies on Fridays. At capacity, the lever is price: if you are booked more than 2 weeks out, raise prices. See `docs/PRICING_GUIDANCE.md`.

## Update 2026-10-10 (5): launch pricing, $99 plan, digital-only, parallel builds

Decisions: all prices are **introductory launch prices for 90 days** and locked for clients who sign inside the window (lock length and later list prices still to decide); the top
care plan is **$99 with a 2-hour monthly cap** (worst case $49.50 an hour); the add-ons are $195 (privacy policy draft), $350 (logo and brand basics), $150 a page (copy) and $85 an
hour (out-of-plan work); **no cold calling**: email and LinkedIn first, a call only when absolutely required (Friday 10am-3pm); up to **3 sites in build at once**.

* **Dropping cold calls cuts the strongest local channel but fits your hours.** Email and LinkedIn at 10 hours a week scale only if templated and batch-approved. Expect lower reply
  rates than calling; the 14-day sprint is how to measure it.
* **"Digital inbound" is worth building properly.** Outbound email that leads to your own properties turns interest into measurable engagement (the Events tab and tracker). A landing page
  for practices with a booking link and a sample medical-practice site would convert replies better than email alone. Not built yet.
* **Parallel builds raise throughput only if your hours per site fall.** The limit of 3 is enforced; a faster rate is not assumed until you measure it (`operator.parallel_efficiency`).
* **Launch pricing as a deadline helps close.** A 90-day window with a lock gives prospects a reason to decide now; set the end date in the proposal.

## Update 2026-10-10 (6): locked terms, landing page, timeline

Decisions: launch window opens **November 1, 2026** and ends **January 30, 2027** (fixed; last day to sign January 29); the **first 100 signers** are locked for **12 months** from signing; regular
prices are to be set (suggestions in `docs/PRICING_GUIDANCE.md`); a **one-page landing page** is built and generated from the spec (`campaign landing`).

* **The cap of 100 will not bind.** At about 2 sites a week for 13 weeks the most you can deliver is about 26. The lock is therefore a fixed-date offer in practice, and the page states the cap and date
  as facts, with no counter or fake scarcity.
* **The lock is a liability you control.** Up to 100 clients at fixed care-plan and hourly prices for a year; at 2 sites a week it is far fewer. Decide whether the lock covers plans and add-ons only (assumed here).
* **Timeline:** today is October 10. Domain warm-up takes weeks, so start it now to be ready November 1. October 18-31 can be the hand-verified pre-launch test (top 30 leads, landing page live, a sample medical-practice site
  if you build one), and live outreach begins November 1 with 13 weeks of runway.
* **The page is the proof piece.** A practice owner will judge the 72-hour promise by this page and by one medical-practice sample, which is still missing.

## What to stop, start, and decide

**Stop** (until the first sale): adding counties and specialties, the price-file analysis (it informs which specialties spend most, not whether a practice
will buy a website), polishing the Sheet, more modules.

**Start (a 14-day validation sprint, about 25 hours total):**
1. Day 1-2: set the offer (fixed price, retainer, three-line proof) and a one-page proposal. Start the sending-domain warm-up now, because it takes weeks.
1b. Also before launch: set a monthly hours cap or fair-use clause on the $50 plan and a time limit on the $20 plan's change.
2. Day 2-4: take the top 30 leads (priority 1, confirmed independent). Verify each by hand: open, owner, site, phone. Add owner name and a direct number or email.
3. Day 4-6: build a quick homepage mock-up for the 10 best.
4. Day 6-14: for the 30: a call, an email with the mock-up, a LinkedIn note, one follow-up. Log every touch and outcome in one sheet.
5. Day 14: decide.

**Go / no-go (set before starting):**
* Continue and invest: 2 or more real conversations, or 1 proposal sent, from 30 contacts.
* Change the offer or the channel: 0-1 conversations but clear objections you can answer.
* Stop or pivot: 0 conversations and no useful objections after all touches.

**Decide now:**
1. Price and retainer (replace the assumptions).
2. Who delivers a 72-hour site and in how many hours (this caps how many sales you can take).
3. How many hours a week this gets while the job search is running.

## What I would build next, if the test passes

1. Contact enrichment and email verification (largest gap).
2. New-practice trigger from NPPES enumeration dates.
3. A pipeline sheet (stages: contacted, replied, call booked, proposal, won, lost) fed by the outreach tasks, with conversion by source and signal.
4. Proposal, contract and invoice templates.
5. Then, and only then: the other 19 counties, other states, packaging.
