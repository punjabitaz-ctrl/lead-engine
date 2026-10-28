# lead-engine

Point it at a place, a segment and a signal. It collects candidates, drops non-buyers, scores them, writes a draft for
each, and fills the Google Sheets template. Then it asks if you want more.

Validate first with `lead-engine-template.xlsx` (no code). The CLI fills that same sheet.

## Building the sites you sell

```
python3 -m leadengine site build intake.json --out site/ --pages 1     # or --pages 3
python3 -m leadengine site qa site/ --intake intake.json               # the delivery checklist, automated
```
The intake JSON is the client's materials (see `examples/sample-practice/intake.json`; built examples in `examples/sample-practice/site-1page/` and `site-3page/`). The build refuses until the client
has supplied everything (services, hours, contact details, privacy policy text, alt text for photos). The same builder makes the free mock-ups for top leads. Generated pages make no external requests.

## Campaigns: the repeatable version

A campaign is one market plus one offer, run through fixed stages with a human gate before anyone is contacted:
`define -> discover -> review (human) -> outreach plan -> batch approval (human) -> paced send -> engagement`.

```
python3 -m leadengine campaign init nj-dental --state NJ --county Middlesex --vertical healthcare-practices
python3 -m leadengine campaign status nj-dental --json     # what is done, what is blocked, what is next (agents start here)
python3 -m leadengine campaign run nj-dental               # next stage size -> campaigns/nj-dental/review/pack-01.csv
python3 -m leadengine campaign run nj-dental --manual my_private_list.csv   # use a hand-assembled list kept outside the repo
python3 -m leadengine campaign approve nj-dental reviewed.csv   # after a human marks Keep / Drop / Unsure
python3 -m leadengine campaign outreach nj-dental --start 2026-10-19   # dated tasks; nothing is sent
python3 -m leadengine campaign batch preview nj-dental 2026-10-19      # read one file, then: batch approve --hash H, then batch send (or batch export)
python3 -m leadengine campaign deal add nj-dental --lead-key <key> --product page1   # after a reply
python3 -m leadengine campaign launch nj-dental --start 2026-11-01   # 90-day introductory pricing, fixed end date; first 100 signers locked for 12 months
python3 -m leadengine campaign landing nj-dental                      # one-page landing page from the spec (see examples/landing_example.html)
python3 -m leadengine campaign deal move nj-dental D001 "Call booked"
python3 -m leadengine campaign deal call nj-dental D001 --reason "..."   # calls are off unless one is absolutely required (Fridays 10-3)
python3 -m leadengine campaign deal pay nj-dental D001 250      # then: deal intake, deal start (refuses until paid and intake complete)
python3 -m leadengine campaign pipeline nj-dental          # funnel, revenue, weekly capacity, in-person eligibility
```

Swap `--state`, `--county`/`--city` and `--vertical` (a pack in `leadengine/data/verticals/`) to run the same process anywhere.

### Any B2B market from a company list

```
python3 -m leadengine campaign init us-entry --state NJ --city "Newark, NJ" --vertical us-market-entry
python3 -m leadengine campaign run us-entry --companies my_list.csv     # exhibitor list, accelerator cohort, CRM or Sales Navigator export
```
The list needs only a `company` column; `website`, `signal` (the reason to contact them now) and `signal_date` make it useful. See
`examples/companies_example.csv` (made up). Use lists you are allowed to use; do not scrape sites whose terms forbid it.
Set `"enrich": {"find_contacts": true}` in the campaign's `spec.json` to read each lead's own website for the emails, phone and LinkedIn page it
publishes (robots.txt respected, one page at a time, cached, capped by `max_contact_sites`). Nothing is guessed and nothing is verified:
found addresses are marked Risky until you run a verifier.

### Marketing emails in approved batches

```
python3 -m leadengine campaign mail plan nj-dental nov-intro --template examples/mail_template_example.txt
python3 -m leadengine campaign mail approve nj-dental nov-intro --batch 1 --hash <hash>   # after reading mail/nov-intro/batch-01.md
python3 -m leadengine campaign mail send nj-dental nov-intro --batch 1 --dry-run         # then without --dry-run; you type SEND
python3 -m leadengine campaign mail sync nj-dental                                       # replies, opt-outs and bounces come back in
```
Templates take `{first_name}`, `{company}`, `{city}` and more. Every email gets your postal address and an opt-out. Sending is paced
(60 to 180 seconds apart), stays inside the send window and a daily cap with warm-up, and is logged in `campaigns/_mail/ledger.csv`.
Anyone who opted out, replied or bounced is skipped. Send through SMTP (an app password) or the Gmail API. Setup: [docs/EMAIL_SENDING.md](docs/EMAIL_SENDING.md).

### Export, enrich and check a list

```
python3 -m leadengine campaign enrich nj-dental                       # fill gaps; check websites, email domains, phones, NPIs, duplicates
python3 -m leadengine campaign quality nj-dental                      # coverage and accuracy report, changes nothing
python3 -m leadengine campaign export nj-dental --format xlsx         # or csv, pdf; --grade A,B --min-confidence 70 --columns full
```
Every row gets an Issues column and a 0-100 Confidence for ranking what to check. A check that could not run says "not checked" instead of
guessing. Only a paid mailbox check (your own ZeroBounce or NeverBounce key) marks an email Valid. Details: [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md).

### After you send: replies, opt-outs and bounces come back in

```
python3 -m leadengine campaign events import nj-dental events.csv   # Date, Event, Lead Key or Email or Company, optional Notes
python3 -m leadengine campaign events report nj-dental              # interest per lead; reply and booking rates by source and signal
```
Opt-outs (including a reply that says "no thanks") and bounces go straight to `suppress.csv`. A reply, booking or form fill stops that lead's
remaining planned tasks, so a follow-up is never sent to someone who already answered. The workbook's Events tab exported as CSV works as input.
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
python3 -m leadengine run --source places --vertical local-services --county Bergen --state NJ   # trades (plumbers, electricians first)
```

Leads are delivered in stages of **59, then 100, then 250** (`--stages`, the last repeats; `--all-stages` runs them back to back; `--target N` for one batch). After each stage it asks whether to continue. Delivered leads are remembered in `.leadengine/seen.json` (`--fresh` ignores it).
Output: `output/leads-<time>-b<N>.csv` plus a filled `.xlsx` copy of the template (its Config tab is set to match the run).

Anywhere in the US: `--city "Austin, TX"` and `--state NJ --zip 07960` work with no setup. Counties and statewide sweeps use
`leadengine/data/geo/<ST>.json`; load every state and county once with `python3 -m leadengine geo build` (downloads the Census Bureau's
public place and county-subdivision lists; on a machine without access, download the two files it names and pass them with `--file`).
`python3 -m leadengine geo show TX --county Travis` lists what a county covers. Until then only NJ is loaded (Middlesex and Somerset by
county, plus a 55-city statewide sweep).

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
git clone <this repo> && cd lead-engine
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
| `places` | `GOOGLE_PLACES_API_KEY`, `--industry` or a pack's `places_queries` | businesses with website, phone and review count; a listing with no website is a confirmed gap | capped per run and per month; **not tested live**; billed per request |
| `--enrich file.csv` | Hunter / Apollo / Indeed-profile exports | size, website, contacts | tested |
| `companies` + `--companies file.csv` | any company list you may use (only `company` required) | B2B leads with hiring or expansion signals and dates | tested |
| `--find-contacts` | internet access to the leads' own websites | emails, phone and LinkedIn the business publishes | tested on canned pages; **not tested live** |

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
tests: `python3 -m unittest discover -s tests` · install as a command: `pip install .` (then `leadengine doctor`)
