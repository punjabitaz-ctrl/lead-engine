# Architecture: one lead process for any place, profession and service

Status: merged to `main`; the contact finder, company lists, pack rules, engagement feedback and packaging are on `claude/finish-lead-engine`. Items marked **built** have tests; **gap** items are not built.

## The model

A **campaign** answers four questions, and nothing else changes between markets:

| Question | Where it lives | Swap it to... |
|---|---|---|
| Where? | `spec.geography` + `leadengine/data/geo/<ST>.json` | any state, county or list of cities |
| Who? | `spec.vertical` = a **pack** in `leadengine/data/verticals/` (+ `tiers`) | dentists, plumbers, firms that are hiring... |
| Why now? | signals + scoring (`config.json`, Config tab) | hiring, no website, thin reviews, expansion... |
| What do we offer, and how do we follow up? | `config.json` sender block + `spec.outreach` | your service, tone, channels, cadence |

## Pipeline and gates

```
define ──> discover ──> enrich/score ──> REVIEW GATE ──> outreach plan ──> HUMAN SENDS ──> engagement ──> learn
 spec       sources       engine          human           dated tasks       approves each     tracker/      (gap)
 built      built*        built           built           built             send              Events sheet
```

* Discover and score are automated. **No contact is made by the tool**, ever: the outreach plan is a task list and each send needs `Approved to send = Y`, set either one by one or
  for a whole day with `campaign batch preview|approve|export` (approve needs the hash of the batch you read; any later edit voids it; flagged drafts block or are left out).
* The review gate is a CSV (or the workbook) with `Decision` = Keep / Drop / Unsure. Only Keep rows reach outreach planning. Dropped leads never resurface (`.state/seen.json`).
* Stages deliver 59, then 100, then 250 leads per pack (`spec.stages`); each run produces one pack.
* State is files, so every stage is resumable and an agent can read `campaign status --json` to know what to do next.
* `*` discover works with the nppes, places and adzuna sources; manual and csv sources are run by hand and fed in with `make_review_pack`.

## Modules

| File | Job |
|---|---|
| `leadengine/campaign.py` | spec, validate, status, run (discover), approve, outreach plan, audit log |
| `leadengine/geo.py` | geography registry: county/city/state -> places |
| `leadengine/packs.py` | vertical packs: tiers of search terms per source |
| `leadengine/batch.py` | batch review of a day's first-contact emails: preview with hash and flags, approve exactly what was read, export for mail merge |
| `leadengine/pipeline.py` | deals after the reply: stages, payment and intake gates before work starts, capacity per week, in-person eligibility, win/loss reasons, conversion by source and signal |
| `leadengine/sitebuilder.py` | intake JSON -> finished 1-page or 3-page static site, plus automated QA (the delivery checklist); also makes the free mock-ups |
| `leadengine/landing.py` | the campaign's own one-page landing page, generated from the spec so prices and dates cannot drift |
| `playbook/` | call script, objections, follow-ups, proposal, agreement, intake form, 72-hour delivery checklist |
| `leadengine/sources.py` | adapters: nppes, places, adzuna, csv postings, manual list, company list (any B2B export) |
| `leadengine/contacts.py` | published contacts from a lead's own website: emails, phone, LinkedIn; robots.txt respected, cached, capped per run |
| `leadengine/events.py` | engagement back into the campaign: import events, suppress opt-outs and bounces, stop sequences, interest and rates by source and signal |
| `leadengine/engine.py`, `scoring.py`, `drafts.py` | ingest, filter, enrich, score, draft |
| `lead-engine-template.xlsx`, `apps-script/`, `tracker/` | no-code sheet, Gmail drafts + reply sync, click/visit tracking |

## Adding a geography

Create `leadengine/data/geo/<ST>.json`: `{"state": "TX", "counties": {"Travis": ["Austin", "Lakeway"]}, "cities": ["Houston", "Dallas"]}`.
`counties` feeds `--county`; `cities` is the statewide sweep. Any single city already works without a file: `--city "Tampa, FL"`.
`leadengine geo build` writes these files for every state from the Census Bureau's code lists. Until it runs, only NJ exists, with Middlesex and Somerset filled in by hand.
ZIP codes need no file: `geography.zips` (or `--zip`) searches NPPES by postal code and Places by "<query> in <ZIP>".

## Adding a vertical

Create `leadengine/data/verticals/<id>.json` with `id`, `label`, `industry`, default `sources`, `tier_order`, and `tiers` whose entries hold
`taxonomies` (NPPES, US healthcare only), `places_queries` (Google Places, any local business) or `professions` (job-board signals).
Optional keys make a market fully configuration: `config` (size basis, thresholds, target employees), `role_rules` (which job titles are the signal),
`ownership_exclude` (names that are not independent buyers) and `templates` (an email set in `data/templates/`).
Examples: `healthcare-practices`, `local-services`, `tech-hiring`, `us-market-entry` (tech companies building a US channel; reads a company list). Then `leadengine campaign init <name> --state XX --city "A, XX" --vertical <id>`.

## Gap audit: what is still tied to the first project

Found by reading every module for assumptions about NJ, healthcare or this one seller. Ordered by how much they block reuse.

| # | Gap | Effect | Fix | Status |
|---|---|---|---|---|
| 1 | Only NJ geography; 19 counties missing | cannot run "all NJ counties" or other states | `leadengine geo build` reads the Census Bureau's place-by-county and county-subdivision lists (public domain) for every state and merges hand-entered names; `--zip` and `--city` need no file | **built** (run once where census.gov is reachable; blocked in this sandbox) |
| 2 | Contact discovery is manual (`--enrich` CSV) | most leads have no email/owner name | `contacts.py`: reads the lead's own site (robots.txt respected) for published emails, tel: links and LinkedIn; ranks own-domain and named addresses first; `--find-contacts` or spec `enrich.find_contacts`. Still to add: a paid verifier | **built** (published contacts; verification still manual) |
| 3 | `HEALTH_SYSTEM` regex lists NJ systems by name | other states' systems slip through as "private" | packs carry `ownership_exclude` regexes; the NJ health-system list still applies to NPPES providers | **built** for packs (`HEALTH_SYSTEM` stays for NPPES) |
| 4 | Size logic counts clinicians (Solo/Small/Medium/Large) | wrong notion for plumbers or agencies | pack `config.size.basis` = clinicians, employees or locations; Size Override still wins | **built** |
| 5 | Email templates and the sheet's Templates tab mention patients, a 72-hour offer and the first seller's portfolio names | every seller's mail would carry them | pack `templates` names a set in `data/templates/` (`b2b.json` added); the default set keeps the workbook in step | **built** for the engine (sheet Templates tab unchanged) |
| 6 | Review workbooks (`tools/build_review.py`) and `manual` lists use specialty/subspecialty | healthcare-shaped | rename to segment/subsegment; call the builder from `campaign run` | gap |
| 7 | Sender details and tracker URL were hard-coded defaults | would send as the first seller | placeholders now; campaign outreach refuses to plan until filled | **built** |
| 8 | No sequence state or opt-out handling | duplicate or ignored follow-ups | planned-lead ledger, shared daily caps, `suppress.csv` (email, domain, company), opt-out line check | **built** |
| 15 | No pipeline after the reply; no close path | leads could not be tracked to a sale | deal pipeline with capacity and in-person rule; playbook templates | **built** |
| 9 | Replies and engagement do not flow back to a campaign | no learning, no suppression from "no thanks" | `campaign events import`: opt-outs (including a reply saying "no thanks") and bounces go to `suppress.csv`; replies, bookings and form fills stop that lead's open tasks | **built** |
| 10 | Scoring weights are fixed by hand | cannot tell which signals convert | `campaign events report`: interest level per lead (same points as the sheet) and reply / booking / opt-out rates by source and signal, with a 200-contact floor before tuning | **built** (reporting; weights still changed by hand) |
| 11 | Compliance covers email basics only | texting, WhatsApp, cold calling and non-US markets have their own rules | per-channel and per-country rule files; block channels until consent/registry checks are recorded | gap (email opt-out and postal address built) |
| 12 | Not packaged | cannot install or license it | `pyproject.toml` with a `leadengine` command; `pip install .` checked in a clean virtualenv | **built** (licence still to choose) |
| 13 | NPPES taxonomy strings and some geography unverified | zero-result queries | run `leadengine doctor` + first live run; fix strings from the warnings | gap (needs network) |
| 14 | Network and keys are manual | agent stalls | `campaign status` lists key blockers; `doctor` lists hosts; keep both in the runbook | **built** (reporting) |

## Roadmap (suggested order)

1. On a networked machine: `leadengine geo build` (#1), a live NPPES run for NJ (#13), then a Places run for trades.
2. Email verification on top of the contact finder (#2), and a first live run of `--find-contacts`.
3. Review workbook naming (#6) and a Sheets Templates tab generated from the pack's template set.
4. After about 200 contacts: tune scoring weights from `campaign events report` (#10).
5. Choose a licence (#12).

## Compliance notes (not legal advice)

Commercial email needs a truthful sender, a postal address and a working opt-out (CAN-SPAM); the engine's template includes all three and
`campaign outreach` blocks when a draft lacks an opt-out line. Phone, text and WhatsApp outreach are governed by separate rules (Do-Not-Call,
TCPA, carrier and platform terms); the plan only schedules calls and LinkedIn touches, and reminds you to check registries first.
Outside the US, consent rules differ (GDPR, CASL, others): review them before pointing a campaign at another country.
