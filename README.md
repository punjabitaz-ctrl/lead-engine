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

```
python3 -m leadengine                                   # prompts for city, industry, profession, signal
python3 -m leadengine run --city "Tampa, FL" --profession "web developer, marketing manager" --target 50
python3 -m leadengine run --source nppes --state NJ --presence presence.csv     # NJ medical offices
```

After each batch it asks `Want 50 more?`. Delivered leads are remembered in `.leadengine/seen.json` (`--fresh` ignores it).
Output: `output/leads-<time>-b<N>.csv` plus a filled `.xlsx` copy of the template (its Config tab is set to match the run).

## Sources

| Source | Needs | Gives | Status |
|---|---|---|---|
| `--postings file.csv` | any job-board export (see `samples/`) | hiring signals | tested |
| `nppes` | internet access to `npiregistry.cms.hhs.gov` (free, no key) | NJ practice name, phone, specialty, authorized official | parser tested on canned data; **API call not tested live** |
| `--presence file.csv` | your manual or tool results: `npi`/`company`, `has_website`, `has_gbp`, `reviews` | confirmed web-presence gaps | tested |
| `--presence-check places` | `GOOGLE_PLACES_API_KEY` | automatic presence lookup | **not tested live**; billed per request |
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

`lead-engine-template.xlsx` Sheets template (Leads, Queue, Call Queue, Events, Dashboard, Templates, Config) ·
`apps-script/Code.gs` optional Gmail-draft / reply-sync helper (untested live) · `samples/` the 2026-10-08 six-city run ·
tests: `python3 -m unittest discover -s tests`
