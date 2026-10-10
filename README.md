# lead-engine

Point it at a place, a segment and a signal. It collects candidates, drops non-buyers, scores them, writes a draft for
each, and fills the Google Sheets template. Then it asks if you want more.

Validate first with `lead-engine-template.xlsx` (no code). The CLI fills that same sheet.

## Campaigns: the repeatable version

A campaign is one market plus one offer, run through fixed stages with a human gate before anyone is contacted:
`define -> discover -> review (human) -> outreach plan -> humans send -> engagement`.

```
python3 -m leadengine campaign init nj-dental --state NJ --county Middlesex --vertical healthcare-practices
python3 -m leadengine campaign status nj-dental --json     # what is done, what is blocked, what is next (agents start here)
python3 -m leadengine campaign run nj-dental               # next stage size -> campaigns/nj-dental/review/pack-01.csv
python3 -m leadengine campaign approve nj-dental reviewed.csv   # after a human marks Keep / Drop / Unsure
python3 -m leadengine campaign outreach nj-dental --start 2026-10-19   # dated tasks; nothing is sent
python3 -m leadengine campaign deal add nj-dental --lead-key <key> --product page1   # after a reply
python3 -m leadengine campaign deal move nj-dental D001 "Call booked"
python3 -m leadengine campaign pipeline nj-dental          # funnel, revenue, weekly capacity, in-person eligibility
```

Swap `--state`, `--county`/`--city` and `--vertical` (a pack in `leadengine/data/verticals/`) to run the same process anywhere.
`playbook/` has the call script, proposal, agreement and delivery checklist. `docs/EXECUTIVE_REVIEW.md` has the business case and `python3 tools/funnel.py` the funnel math.
See `docs/ARCHITECTURE.md` for the model and the gap list, and `docs/AGENT_RUNBOOK.md` for how an agent drives it.
`campaigns/` holds lead data and sender details, so it is git-ignored except `campaigns/README.md`.

## Two different ideas, kept separate

- **Signal strength** (`hot / warm / cold`): how strong the reason to contact them is. Computed when the lead is found.
  Examples: a fresh hiring post, or a confirmed missing website and Google profile.
- **Interest level** (`Hot / Warm / Cold / Opted out`): how they engage with *your* digital properties (clicks, visits,
  form fills, replies, bookings). Scored in the sheet from the **Events** tab. New leads start at "No contact yet".

## Run it

First: `python3 -m leadengine doctor` lists which data hosts this environment can reach and which keys are set (no secret values printed).

```
python3 -m leadengine                                   # prompts for city, industry, profession, signal
python3 -m leadengine run --city "Tampa, FL" --profession "web developer, marketing manager" --target 50
python3 -m leadengine run --source nppes --county Middlesex --county Somerset --tier 1 --presence-check places   # first test area
python3 -m leadengine run --source nppes --state NJ --tier 1 --presence-check places   # statewide city sweep (top ~55 cities only)
python3 -m leadengine run --source nppes --state NJ --presence presence.csv             # or import hand-checked results
```

Leads are delivered in stages of **59, then 100, then 250** (`--stages`, the last repeats; `--all-stages` runs them back to back; `--target N` for one batch). After each stage it asks whether to continue. Delivered leads are remembered in `.leadengine/seen.json` (`--fresh` ignores it).
Output: `output/leads-<time>-b<N>.csv` plus a filled `.xlsx` copy of the template (its Config tab is set to match the run).

Counties: `--county Middlesex --county Somerset` (municipalities and USPS place names from `leadengine/data/geo/NJ.json`, written from memory
and unverified; the other 19 NJ counties and other states are not loaded yet: add `data/geo/<ST>.json`, see `docs/ARCHITECTURE.md`).

Segments (`--tier`, from the vertical pack `leadengine/data/verticals/healthcare-practices.json`): **focus** (default) cardiology + ophthalmology (pitch: site and local-search quality; signals: weak site, thin reviews, slow mobile page) · **1** dentists, physical therapists, mental health, primary care ·
**2** gastroenterology, orthopaedics, cardiology (high referral volume per cited studies) · **3** unvalidated cost-of-care candidates ·
`--taxonomy "A, B"` overrides. The specialty strings are not yet verified against the live registry; the first live run warns on any
that return nothing.

## Candidate lists

The hand-assembled lead lists for named practices (Middlesex and Somerset counties, NJ) are kept in a private copy and are not in this public version. Put CSV files
with the columns in `data/candidates/README.md` into `data/candidates/`, then:

```
python3 tools/run_lists.py        # runs the engine, writes lists/*.xlsx and *.csv
python3 tools/build_review.py lists
python3 tools/build_template.py lead-engine-template.xlsx   # regenerates the Sheets template
```

Primary care note: system-owned locations (RWJBarnabas, Hackensack Meridian, Atlantic Health, Saint Peter's, Hunterdon) belong in their own sub-specialty marked Large
with the owner as the basis, so `--exclude-large` or the Size filter hides them.

## Filtering large groups

Every lead gets a **Size Class**: Solo (1 clinician), Small (2-5), Medium (6-15), Large (16+) or Unknown. Thresholds are on the Config tab (rows 112-113).
Enter the clinician count in **Providers (est.)**, or set **Size Override** (for example Large for a chain or dental group you can see is big).
On the Leads tab filter the Size Class column to hide Large rows, or set Config B114 to Y to keep Large practices out of the Queue and Call Queue.
On the command line, `--exclude-large` drops them. Unknown is not Large: count the clinicians when you review.

## Running it on your own computer

The tool needs only Python 3 (openpyxl is optional, for the filled .xlsx). On a machine with normal internet access none of the network blocks apply:

```
git clone <this repo> && cd lead-engine && git checkout claude/lead-generation-system-pbvuy8
python3 -m leadengine doctor
python3 -m leadengine run --source nppes --county Middlesex --county Somerset --audit
```

## Sources

| Source | Needs | Gives | Status |
|---|---|---|---|
| `--postings file.csv` | any job-board export (see `examples/postings_example.csv`) | hiring signals | tested |
| `nppes` | internet access to `npiregistry.cms.hhs.gov` (free, no key) | NJ practice name, phone, specialty, authorized official | parser tested on canned data; **API call not tested live** |
| `manual` + `--manual file.csv` | a hand-assembled practice list (practice, specialty, city, address, phone, priority 1-3, evidence, source, providers, size_override) | ranks by independence evidence first; keep real-name lists out of git (`private/` is ignored) | tested |
| `--presence file.csv` | your manual or tool results: `npi`/`company`, `has_website`, `has_gbp`, `reviews` | confirmed web-presence gaps | tested |
| `--presence-check places` | `GOOGLE_PLACES_API_KEY` | automatic presence lookup, cached, with per-run and monthly caps | caps/cache tested; **API call not tested live**; billed per request |
| `adzuna` | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | hiring signals | **not tested live** |
| `places` | `GOOGLE_PLACES_API_KEY`, `--industry` | businesses with website + phone | **not tested live** |
| `--enrich file.csv` | Hunter / Apollo / Indeed-profile exports | size, website, contacts | tested |

## NJ medical offices with no web presence: what to know

- The registry has **no emails**. These practices are reachable by phone, mail or in person, so the sheet adds a
  **Call Queue** tab and phone/postcard scripts. Email only works once you find a verified address.
- A lead is only marked "No Presence" after a **confirmed** gap. Unchecked providers are `cold` and each row carries two
  links for a 30-second manual check.
- "Privately owned" is a name heuristic (`leadengine/filters.py`): health-system names are dropped, and individuals must be
  flagged sole proprietor. Ownership is not in the registry.
- Physician advertising in NJ is governed by N.J.A.C. 13:35-6.10. Get legal review for anything patient-facing.

## Files

`docs/SETUP.md` network, Google key, sending-domain checklist · `tracker/` click/visit tracker · `lead-engine-template.xlsx` Sheets template (Leads, Queue, Call Queue, Events, Dashboard, Templates, Config) ·
`apps-script/Code.gs` optional Gmail-draft / reply-sync helper (untested live) · `examples/` a tiny made-up postings file ·
tests: `python3 -m unittest discover -s tests`
