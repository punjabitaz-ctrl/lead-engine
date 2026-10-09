# lead-engine

Point it at a city, industry, profession and interest level. It collects candidates, filters out non-buyers, scores
them, writes a first-email draft for each, and hands you a ready-to-use sheet. Then it asks if you want more.

Validate first: `lead-engine-template.xlsx` (Google Sheets) is the no-code version. The CLI fills that same sheet.

## Run it

```
python3 -m leadengine                 # prompts for city, industry, profession, interest level
python3 -m leadengine run --city "Tampa, FL" --city "Austin, TX" --industry "logistics" \
    --profession "web developer, marketing manager" --interest warm --target 50
```

Interest level: `hot` = fresh hiring signal (30 days) or 2+ postings · `warm` = within 90 days · `any`.
After each batch it asks `Want 50 more?`. Leads already delivered are remembered in `.leadengine/seen.json`
(`--fresh` ignores that). Output: `output/leads-<time>-b<N>.csv` and a filled `.xlsx` copy of the template.

## Data sources (set the ones you have)

| Source | Needs | Gives | Status |
|---|---|---|---|
| `--postings file.csv` | any job-board export (`samples/indeed_postings_2026-10-08.csv` shows the columns) | hiring signals | tested |
| `adzuna` | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | hiring signals, 50/page | written from the API docs, **not tested live** |
| `places` | `GOOGLE_PLACES_API_KEY`, `--industry` | businesses with website + phone | written from the API docs, **not tested live**; billed per request |
| `--enrich file.csv` | Hunter / Apollo / Indeed-profile exports (`samples/enrichment_2026-10-08.csv`) | size, website, contacts | tested |
| `--audit` | internet | flags sites with no mobile tag, no HTTPS, stale footer year (`PAGESPEED_API_KEY` adds a mobile score) | logic tested offline only |

## What it does not do

- Find email addresses. Postings give company names, not people. Add contacts with `--enrich`, verify them, then the
  sheet's Grade and Queue take over. Until then every lead scores at most about 45 and shows Grade C/D.
- Know company size. The blocklist (`leadengine/data/enterprise_blocklist.txt`) is a judgement-call heuristic. Edit it.
- Send anything. Drafts are text. You review and send.

## Tests

`python3 -m unittest discover -s tests`

## Files

`lead-engine-template.xlsx` Sheets template · `apps-script/Code.gs` optional Gmail-draft helper · `samples/` the
2026-10-08 six-city sample run.
