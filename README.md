# lead-engine

Point it at a place, a segment and a signal. It collects candidates, drops non-buyers, scores them, writes a draft for
each, and fills the Google Sheets template. Then it asks if you want more.

Validate first with `lead-engine-template.xlsx` (no code). The CLI fills that same sheet.

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

Counties: `--county Middlesex --county Somerset` (municipalities and USPS place names from `leadengine/data/nj_counties.json`, written from memory
and unverified; the other 19 counties are not loaded yet).

Segments (`--tier`, from `leadengine/data/segments.json`): **focus** (default) cardiology + ophthalmology (pitch: site and local-search quality; signals: weak site, thin reviews, slow mobile page) · **1** dentists, physical therapists, mental health, primary care ·
**2** gastroenterology, orthopaedics, cardiology (high referral volume per cited studies) · **3** unvalidated cost-of-care candidates ·
`--taxonomy "A, B"` overrides. The specialty strings are not yet verified against the live registry; the first live run warns on any
that return nothing.

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
| `--postings file.csv` | any job-board export (see `samples/`) | hiring signals | tested |
| `nppes` | internet access to `npiregistry.cms.hhs.gov` (free, no key) | NJ practice name, phone, specialty, authorized official | parser tested on canned data; **API call not tested live** |
| `manual` + `--manual file.csv` | a hand-assembled practice list (practice, specialty, city, address, phone, priority 1-3, evidence, source) | ranks by independence evidence first; keep real-name lists out of git (`private/` is ignored) | tested |
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
`apps-script/Code.gs` optional Gmail-draft / reply-sync helper (untested live) · `samples/` the 2026-10-08 six-city run ·
tests: `python3 -m unittest discover -s tests`
