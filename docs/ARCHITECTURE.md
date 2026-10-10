# Architecture: one lead process for any place, profession and service

Status: branch `dev/generalized-engine` (not merged to `main`). Items marked **built** have tests; **gap** items are not built.

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

* Discover and score are automated. **No contact is made by the tool**, ever: the outreach plan is a task list and each send needs `Approved to send = Y`.
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
| `leadengine/sources.py` | adapters: nppes, places, adzuna, csv postings, manual list |
| `leadengine/engine.py`, `scoring.py`, `drafts.py` | ingest, filter, enrich, score, draft |
| `lead-engine-template.xlsx`, `apps-script/`, `tracker/` | no-code sheet, Gmail drafts + reply sync, click/visit tracking |

## Adding a geography

Create `leadengine/data/geo/<ST>.json`: `{"state": "TX", "counties": {"Travis": ["Austin", "Lakeway"]}, "cities": ["Houston", "Dallas"]}`.
`counties` feeds `--county`; `cities` is the statewide sweep. Any single city already works without a file: `--city "Tampa, FL"`.
Only NJ exists, with Middlesex and Somerset filled in (from memory, unverified). Loading all 21 NJ counties needs the Census place-to-county
tables, which this environment could not reach (see gaps).

## Adding a vertical

Create `leadengine/data/verticals/<id>.json` with `id`, `label`, `industry`, default `sources`, `tier_order`, and `tiers` whose entries hold
`taxonomies` (NPPES, US healthcare only), `places_queries` (Google Places, any local business) or `professions` (job-board signals).
Examples: `healthcare-practices`, `local-services`, `tech-hiring`. Then `leadengine campaign init <name> --state XX --city "A, XX" --vertical <id>`.

## Gap audit: what is still tied to the first project

Found by reading every module for assumptions about NJ, healthcare or this one seller. Ordered by how much they block reuse.

| # | Gap | Effect | Fix | Status |
|---|---|---|---|---|
| 1 | Only NJ geography; 19 counties missing | cannot run "all NJ counties" or other states | build `data/geo/*.json` from Census place-county tables + USPS names; verify against NPPES results | gap (needs network) |
| 2 | Contact discovery is manual (`--enrich` CSV) | most leads have no email/owner name | add enrichment adapters: website contact-page scrape, Hunter/Apollo-style API, email verification, LinkedIn lookup | gap |
| 3 | `HEALTH_SYSTEM` regex lists NJ systems by name | other states' systems slip through as "private" | move ownership rules into the pack; derive owner from NPPES organization/parent data and CMS/state licence data | gap |
| 4 | Size logic counts clinicians (Solo/Small/Medium/Large) | wrong notion for plumbers or agencies | make the size basis a pack setting (clinicians, employees, locations); keep Size Override | gap |
| 5 | Email templates and the sheet's Templates tab mention patients, a 72-hour offer and the first seller's portfolio names | every seller's mail would carry them | template sets per campaign (`templates.json` per pack/offer) and a generated sheet; `tools/build_template.py` reads them | gap |
| 6 | Review workbooks (`tools/build_review.py`) and `manual` lists use specialty/subspecialty | healthcare-shaped | rename to segment/subsegment; call the builder from `campaign run` | gap |
| 7 | Sender details and tracker URL were hard-coded defaults | would send as the first seller | placeholders now; campaign outreach refuses to plan until filled | **built** |
| 8 | No sequence state or opt-out handling | duplicate or ignored follow-ups | planned-lead ledger, shared daily caps, `suppress.csv` (email, domain, company), opt-out line check | **built** |
| 9 | Replies and engagement do not flow back to a campaign | no learning, no suppression from "no thanks" | import Gmail/Events data into the campaign: auto-suppress opt-outs, advance or stop the sequence, report reply/booking rate per source and signal | gap |
| 10 | Scoring weights are fixed by hand | cannot tell which signals convert | log outcomes per lead; compare conversion by signal/source after ~200 contacts; tune weights | gap |
| 11 | Compliance covers email basics only | texting, WhatsApp, cold calling and non-US markets have their own rules | per-channel and per-country rule files; block channels until consent/registry checks are recorded | gap (email opt-out and postal address built) |
| 12 | Not packaged | cannot install or license it | `pyproject.toml`, versioned releases, licence, a clean-install test | gap |
| 13 | NPPES taxonomy strings and some geography unverified | zero-result queries | run `leadengine doctor` + first live run; fix strings from the warnings | gap (needs network) |
| 14 | Network and keys are manual | agent stalls | `campaign status` lists key blockers; `doctor` lists hosts; keep both in the runbook | **built** (reporting) |

## Roadmap (suggested order)

1. Unblock network, then: all NJ counties (#1), live NPPES run (#13), hospital price files for the specialty-economics view.
2. Contact discovery and email verification (#2): without it the outreach plan has little to act on.
3. Template sets and generic sizing/ownership per pack (#3-#6): lets a second seller or vertical run without edits.
4. Feedback loop (#9, #10): replies and bookings change the campaign, not just a spreadsheet.
5. Packaging and licence (#12).

## Compliance notes (not legal advice)

Commercial email needs a truthful sender, a postal address and a working opt-out (CAN-SPAM); the engine's template includes all three and
`campaign outreach` blocks when a draft lacks an opt-out line. Phone, text and WhatsApp outreach are governed by separate rules (Do-Not-Call,
TCPA, carrier and platform terms); the plan only schedules calls and LinkedIn touches, and reminds you to check registries first.
Outside the US, consent rules differ (GDPR, CASL, others): review them before pointing a campaign at another country.
