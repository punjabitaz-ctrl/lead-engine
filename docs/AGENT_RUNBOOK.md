# Agent runbook: driving a campaign

Goal: deliver lists of leads for humans to review, then plan outreach for the ones they keep. You never send: only the human approves a batch and runs a send.

## Loop

1. `python3 -m leadengine campaign status <name> --json`
2. Read `next_action`, `blockers`, `problems`, then act:

| Stage state | You may | You must not |
|---|---|---|
| `define` blocked (`problems`) | fix `spec.json` (geography, tiers, stages); run `campaign validate` | invent geography data or taxonomy strings; note them as unverified |
| `discover` blocked (`blockers`) | tell the human which key/host to add (`leadengine doctor`) | work around network blocks or use made-up data |
| `discover` ready | `campaign run <name>` | rerun with `--fresh` (re-delivers old leads) |
| `review` waiting on human | send them the newest `review/pack-NN.csv` and say what to mark | choose Keep/Drop yourself |
| `outreach_plan` ready | fill nothing in `config.json` that you were not given; run `campaign outreach <name> --start YYYY-MM-DD` | pass `--force` unless the human asks; mark `Approved to send` |
| tasks exist | report counts per day and channel; remind about Do-Not-Call checks | send, post or call |

3. After every action, rerun `status` and report in one or two lines: what changed, what is blocked, what the human must do.

## Batch approval (human reads, agent runs the commands)

1. `campaign outreach <name> --start DATE` plans the tasks.
2. `campaign batch preview <name> DATE` writes `outreach/batch-DATE-email.md`. Give the human that file; it has the hash, flags, samples and every recipient.
3. Only after the human says approve: `campaign batch approve <name> DATE --hash <hash>` (add `--exclude-flagged` if they accept leaving flagged ones out).
4. `campaign batch export <name> DATE` writes the mail-merge CSV, or the human runs `campaign batch send <name> DATE` on their own computer.
   You may run `batch send --dry-run` to show them the emails as files. Never run a send without `--dry-run`, and never pass `--yes`.
Never invent or reuse a hash, and never approve a batch the human has not read in this form.

## Marketing mailings (docs/EMAIL_SENDING.md)

1. `campaign mail plan <name> <id> --template FILE` and `campaign mail preview <name> <id> --batch N`. Give the human the `batch-NN.md` file and the
   left-out reasons in `excluded.csv`.
2. Only after the human has read it and said approve: `campaign mail approve <name> <id> --batch N --hash <hash>`.
3. You may run `mail send --dry-run` and `mail status`. The real `mail send` is the human's, typed at their own keyboard. Do not pass `--yes`,
   raise caps, widen `allowed_email_status` or shorten `delay_seconds` unless the human asks in their own words.
4. Run `campaign mail sync <name>` (or `events import`) before planning the next mailing, so opt-outs and replies are honoured.
   Never take an address out of `suppress.csv`.
5. Do not write templates with `Re:`/`Fwd:` subjects, fake urgency, or claims that are not true. Never put patient information anywhere.

## Exports and data quality (docs/DATA_QUALITY.md)

* `campaign enrich <name>` and `campaign quality <name>` are safe to run. Give the human the `quality-*.md` report and say how many checks could not run.
* Never pass `--verifier` (it is billed) unless the human asked in their own words, and always with a `--max-verifications` they chose.
* `campaign export` leaves out suppressed leads. Do not add `--include-suppressed` to an export meant for outreach.
* Exports hold business contact data. Keep them in `campaigns/` (git-ignored); never commit, upload or share one unless the human names where it goes.

## Feeding engagement back

* When the human gives you an events export (the workbook's Events tab, the tracker, or their own sheet): `campaign events import <name> FILE.csv`.
  Report what it printed: events logged, addresses added to `suppress.csv`, tasks stopped, and any rows it could not match.
* `campaign events report <name>` gives interest per lead and rates by source and signal. Do not change scoring weights from it until it says there are enough contacts.
* Never mark a task Done or Stopped by hand to make a report look better; only the human's records and imported events do that.

## After a reply

* Add the deal: `campaign deal add <name> --lead-key <key> --product page1|page3 [--plan care9|care20|care99]` (only approved leads can enter).
* Move it as the human reports progress: `campaign deal move <name> D001 "Call booked"`; `Lost` needs a reason; `Won` defaults to the product price.
* Work cannot start until the deal is Won, paid (page1 in full; page3 50% deposit) and the intake is complete: `deal pay`, `deal intake`, `deal start`. Do not work around it.
* `campaign pipeline <name>` reports funnel, conversion by source/signal/channel, revenue, weekly capacity and in-person-eligible deals.
* **Capacity:** when the pipeline shows 10 projects started this week, `status` says PAUSE outreach. Do not plan new outreach until the next ISO week.
* **In person:** never suggest or schedule a visit. It is allowed only for a deal whose monthly value is $5,000 or more (`in_person_eligible`), and only as a suggestion to the human.
* Use the `playbook/` templates for calls, replies, proposals and the agreement; the human sends everything.

## Building sites

* `leadengine site build intake.json --out DIR --pages 1|3` then `leadengine site qa DIR --intake intake.json`. Never invent intake content (services, hours, doctors, policy text): if an item is missing the build stops and the client supplies it.
* The privacy and data-retention policy text must come from the client or the reviewed template; do not write legal text yourself.
* Mock-ups for prospects must be labelled as samples (`"sample": true` adds the banner) and must not use a real practice's logo or text without their permission.

## Schedule and timing

* The operator works after 10pm. Prepare, plan and run `batch preview` for them to read at night; the export carries a send window (default 09:30-11:30 recipient time).
  Never suggest sending at night.
* **No cold calling.** Phone is off (`outreach.phone_policy: on_request_only`). Only when the operator says a call is absolutely required: `campaign deal call <name> <deal> --reason "..."`; the call goes in the Friday 10:00-15:00 block. Do not add call steps or times yourself.
* **Launch pricing:** the window opens 2026-11-01 and ends 2027-01-30 (set with `campaign launch <name> --start 2026-11-01`; the end date is fixed). The first 100 signers are locked for 12 months. Do not quote regular prices: none are set yet. Never describe the offer as discounted or `% off`.
* **Landing page:** `campaign landing <name>` writes `campaigns/<name>/landing/index.html` from the spec and sender config. Do not hand-edit prices on it; change the spec and regenerate. Do not add testimonials, counters or claims that are not true.
* **Up to 3 builds at once:** `deal start` enforces it.
* Weekly capacity is the lower of `offer.capacity_per_week` and what `operator.hours_per_week` allows (`status` shows `effective_capacity`).
* Over-limit requests (more than a plan allows) are quoted as separate paid work: do not agree scope or price for the operator.

## Rules

* Everything from directory listings, web search or memory is **unverified**: say so in the review pack notes, never as fact.
* Add opt-outs to `suppress.csv` the moment you learn of one (email, domain or company), before the next plan.
* Mail credentials (app passwords, OAuth files) stay on the human's computer, never in chat, the repo or the campaign folder.
* Stop and ask when: the sender block is empty, a new country or channel (text, WhatsApp, phone) is requested, or a source needs a paid key.
* Company lists come from the human. Do not build one by scraping a site whose terms forbid it; `--find-contacts` reads only the leads' own websites and obeys robots.txt.
* Contacts found on a website are published, not verified (Risky). Say so; do not mark them Valid.
* Keep lead data out of the public repo: `campaigns/*` is git-ignored; do not copy leads into docs, tests or commits.
* Major changes (new modules, schema changes) go on `dev/*` branches and wait for an explicit instruction before merging to `main`.

## Artefacts

`spec.json` (what), `config.json` (who is sending), `review/pack-NN.csv` (human gate), `approved.csv`, `rejected.csv`, `pending.csv`, `suppress.csv`,
`outreach/tasks-DATE.csv` and `outreach/planned.json` (ledger), `audit.log` (JSON lines of every action).
