# Agent runbook: driving a campaign

Goal: deliver lists of leads for humans to review, then plan outreach for the ones they keep. Never contact anyone.

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
4. `campaign batch export <name> DATE` writes the mail-merge CSV. The human sends; you never do.
Never invent or reuse a hash, and never approve a batch the human has not read in this form.

## After a reply

* Add the deal: `campaign deal add <name> --lead-key <key> --product page1|page3 [--plan care9|care20|care50]` (only approved leads can enter).
* Move it as the human reports progress: `campaign deal move <name> D001 "Call booked"`; `Lost` needs a reason; `Won` defaults to the product price.
* Work cannot start until the deal is Won, paid (page1 in full; page3 50% deposit) and the intake is complete: `deal pay`, `deal intake`, `deal start`. Do not work around it.
* `campaign pipeline <name>` reports funnel, conversion by source/signal/channel, revenue, weekly capacity and in-person-eligible deals.
* **Capacity:** when the pipeline shows 10 projects started this week, `status` says PAUSE outreach. Do not plan new outreach until the next ISO week.
* **In person:** never suggest or schedule a visit. It is allowed only for a deal whose monthly value is $5,000 or more (`in_person_eligible`), and only as a suggestion to the human.
* Use the `playbook/` templates for calls, replies, proposals and the agreement; the human sends everything.

## Rules

* Everything from directory listings, web search or memory is **unverified**: say so in the review pack notes, never as fact.
* Add opt-outs to `suppress.csv` the moment you learn of one (email, domain or company), before the next plan.
* Stop and ask when: the sender block is empty, a new country or channel (text, WhatsApp, phone) is requested, or a source needs a paid key.
* Keep lead data out of the public repo: `campaigns/*` is git-ignored; do not copy leads into docs, tests or commits.
* Major changes (new modules, schema changes) go on `dev/*` branches and wait for an explicit instruction before merging to `main`.

## Artefacts

`spec.json` (what), `config.json` (who is sending), `review/pack-NN.csv` (human gate), `approved.csv`, `rejected.csv`, `pending.csv`, `suppress.csv`,
`outreach/tasks-DATE.csv` and `outreach/planned.json` (ledger), `audit.log` (JSON lines of every action).
