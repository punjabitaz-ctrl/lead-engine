# Commercial review: what stands between this and a tool people pay for

Reviewed 2026-10-28, after the email sender (PR #6) and the exports, enrichment and accuracy checks (this change). It builds on
[EXECUTIVE_REVIEW.md](EXECUTIVE_REVIEW.md) (2026-10-10) and does not repeat it. Not legal advice: the legal points are the questions to take to a lawyer.

## The short answer

The engine is now a complete **single-operator** tool: find, score, review, enrich, check, export, email in approved batches, read replies back,
track deals. Every stage is tested, but only against stand-ins. **It has never produced a real lead, a real check or a real email**, because this
build environment has no open network. That is the gap that matters most, and no amount of extra code closes it.

What it is closest to being sold as depends on which business you mean. Those are three different products:

| Model | What the buyer gets | Distance from today |
|---|---|---|
| A. Your own prospecting engine for AYiN's website and care-plan offer | leads, emails, a pipeline | **Close.** Needs one live run, a sending domain, and the first 50 emails. |
| B. Lead lists or done-for-you outreach sold to agencies and local service firms | an enriched, checked list or a booked-meeting service | **Medium.** Needs licensed contact data, legal review of data sources and resale, and a delivery process. |
| C. Self-serve software (SaaS) | a login, a UI, billing | **Far.** Needs a web app, accounts, a database, hosting, billing, support, and a reason to pick it over established tools. |

Recommendation: run A now, use what it proves to decide on B, and do not start C until A and B show people pay.

## Where each stage stands now

| Stage | State on 2026-10-28 | Score (was) |
|---|---|---|
| Generate | NPPES, Census geography, Places, Adzuna, company lists, manual lists; any vertical and US geography via packs | 5/10 (4): built for any market, still never run live |
| Qualify | score, size, signals, grade, reasons | 4/10 (4): weights are still guesses until replies come back |
| Sort and review | review packs, hash approvals | 7/10 (7) |
| Enrich and check | contact finder, DNS mail check, website live/parked/redirect, NPPES status, phone and NPI rules, duplicates, confidence, stale flags, paid verifier hook | 6/10 (new): good rules, no live results yet |
| Reach | paced batch email with CAN-SPAM footer, caps, warm-up, bounce stop, ledger, SMTP and Gmail API | 6/10 (3): no sending domain set up yet |
| Close | deal pipeline, capacity, payment and intake gates, playbook | 5/10 (1) |
| Measure | events import, reply sync, interest and rates by source and signal | 4/10 (2): no data yet |
| Export and share | CSV, Excel, PDF with filters and suppression | 7/10 (new) |

## What is missing, in the order it blocks money

### 1. Proof (blocks everything)
* One live NJ medical run on a machine with open network: `leadengine doctor`, then `campaign run`, then `campaign enrich`, then `campaign quality`.
  The quality report gives the first real numbers: how many practices publish an email, how many sites are live, how many NPIs are active.
* Expect email coverage to be the weak point. Many medical practices publish only a phone number and a contact form. Measure it before deciding
  anything else, because it decides whether model B needs bought data.
* NPPES taxonomy strings and some geography are still unverified (gap #13). A wrong string returns zero results rather than an error.

### 2. Data you are allowed to use the way you plan to use it
* **Google Places.** Google's terms restrict storing Places content and using it to build a database or list for others. This change makes the
  cache expire after 30 days, which is closer, but the strict reading allows storing only place IDs. For model A (your own outreach) the risk is low.
  For model B (selling lists) do not include Places-derived fields until a lawyer has read the current Maps Platform terms.
* **Scraped contact details.** The finder reads only what a business publishes, respects robots.txt, and keeps nothing from sites that say their
  addresses are not for commercial email. Individual site terms can still forbid collection. Fine for A; for B, prefer licensed data.
* **Privacy law.** Since 2023 California's privacy law covers business contact details of California residents. Selling lists of people you have no
  relationship with can make you a data broker, which several states (California, Texas, Oregon, Vermont) require to register. Needed for B, not A.
* NPPES and Census data are public and free to reuse.

### 3. Deliverability (blocks A's results)
* A sending domain separate from your main one, with SPF, DKIM and DMARC, warmed up slowly. The caps and warm-up are built; the domain is not.
* A paid mailbox check before the first send (ZeroBounce or NeverBounce hook is built; it needs your key and budget).
* Opt-out today is by reply or email to an address, which meets CAN-SPAM. A hosted one-click unsubscribe page becomes necessary only at bulk volumes
  (Gmail's and Yahoo's bulk-sender rules), far above the default 30 a day.

### 4. Product gaps that only matter for B or C
* **Interface.** It is a command-line tool working on CSV files. A buyer of B gets files; a buyer of C needs a web app.
* **Storage and concurrency.** CSV files and a JSON audit log suit one operator. Two people, or a scheduled job running alongside a person, need a database.
* **CRM sync.** Nothing pushes leads or replies to HubSpot or Salesforce. The CSV and Excel exports import into both by hand; an API sync is the next step for B.
* **Scheduling and monitoring.** Runs are manual. Nothing alerts you when a source breaks, a key expires or the bounce stop trips.
* **Multi-tenant separation, billing, support.** None. C only.
* **Competition.** Established prospecting and sending tools already cover lists, enrichment and sequencing. The engine's edge is narrow: vertical packs
  for local practices and trades, public-registry signals (NPI, hiring posts, missing websites), and a human approval gate. That edge suits a service (B)
  better than software (C).

### 5. Engineering hygiene
* **CI** now runs the tests on each push and pull request (Python 3.9 and 3.12). Turn it off in the Actions tab if you would rather not.
* **No licence.** Without one, nobody else may legally use or modify the code. Choose before sharing it (gap #12).
* **Live-only code paths are unproven:** SMTP and Gmail sending, IMAP and Gmail reply sync, DNS and NPPES checks, the paid verifiers' real responses.
  Each is written to the provider's documentation and tested with stand-ins.
* Releases: version 0.4.0, installable with `pip install .`, not published.

## What this change closed
* Export to CSV, Excel and PDF from any list, with filters, suppression and formula-safe cells (gap #17).
* Enrichment and accuracy checks with issues, a confidence score, stale-row flags and a quality report; a paid mailbox check that only runs with your key and a cap (gap #18).
* Places cache expiry (gap #19).

## Decisions for you
1. Which model to aim at first: A (your own outreach), B (lists or a service for others), or C (software). This review assumes A.
2. Whether to spend on a mailbox verifier before the first send, and the cap per run.
3. A licence, if anyone other than you will use the code.
4. Whether to keep the new CI workflow.
