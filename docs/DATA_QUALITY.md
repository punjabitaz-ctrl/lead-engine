# Exports, enrichment and accuracy checks

## Export a list

```
python3 -m leadengine campaign export nj-dental --format xlsx                     # approved leads, the contact columns
python3 -m leadengine campaign export nj-dental --format pdf --grade A,B           # a printable table of the best leads
python3 -m leadengine campaign export nj-dental --format csv --list all --columns full
python3 -m leadengine campaign export nj-dental --format csv --min-confidence 70 --email-status Valid,Risky --has-email
python3 -m leadengine export some-leads.csv --format xlsx                          # any lead CSV, outside a campaign
```

* `--list`: `approved` (default), `pending`, `rejected`, `review` (every review pack), `all`, or a CSV path. A lead that appears in two lists is exported once.
* `--columns`: `contact` (default: company, contact, email and status, phone, website, place, score, grade, signal, reason, confidence, issues),
  `full` (every column except drafts and review bookkeeping), or your own list such as `"Company,Email,Phone"`.
* Opt-outs, bounces and do-not-contact entries in `suppress.csv` are left out unless you add `--include-suppressed`.
* Files go to `campaigns/<name>/exports/` (git-ignored with the rest of `campaigns/`) unless you pass `--out`.

| Format | What you get |
|---|---|
| CSV | UTF-8 with a byte-order mark so Excel reads accents. Cells that start with `=`, `+`, `-` or `@` get a leading `'`, so a scraped name can never run as a spreadsheet formula. |
| Excel | A Leads sheet with a bold, frozen, filterable header, sized columns and real numbers for Score and Confidence, plus an About sheet: campaign, date, filters, counts and the data note. No extra install needed. |
| PDF | Landscape US Letter, page numbers, shaded rows. Long cells end in "..." (the CSV and Excel keep everything). Up to 16 columns; the default PDF set is 13. |

## Enrich and check a list

```
python3 -m leadengine campaign enrich nj-dental                       # free steps on approved.csv
python3 -m leadengine campaign enrich nj-dental --list review --steps websites,email
python3 -m leadengine campaign quality nj-dental                      # report only: changes nothing, uses no network
```

| Step | What it does | Free? |
|---|---|---|
| offline (always) | email syntax, disposable and role addresses, free mail, email domain vs website; NANP phone rules and formatting; NPI check digit; state code; listing sites (Yelp, Facebook...) given as a website; capitalised registry names; names that are not a person; duplicates by key, email, phone, or name and city | yes |
| `contacts` | rows with a website and no email: reads the business's own site for published email, phone and LinkedIn (robots.txt respected, cached, `--max-sites`) | yes |
| `websites` | the site answers, is not a parked or for-sale page, and does not redirect to a different business | yes |
| `email` | the email domain has mail servers (DNS over HTTPS). No mail servers or no such domain makes the address Invalid | yes |
| `npi` | the NPI is active in the NPPES registry and the registry name resembles the company or contact | yes |
| `verify` | a mailbox check with your own ZeroBounce or NeverBounce key. The only step that can mark an address Valid | **paid**, needs `--verifier` and `--max-verifications N` |

Each row gains `Phone (formatted)`, `Email Check`, `Website Check`, `NPI Check`, `Issues`, `Confidence`, `Last Verified` and `Checked`.
The list is rewritten with a `.bak` copy of the previous version. Rows are never dropped: problems are flagged for you to decide.

Rules it follows:
* A check that could not run (no network, a timeout) says `not checked`. It never counts as a pass or a fail, and does not set `Last Verified`.
* Free checks never upgrade an address. Addresses read off a business's site stay Risky until a paid mailbox check says Valid.
* Rows not checked in 90 days are flagged, because practices move, close and change staff.
* `Confidence` (0 to 100) starts at 100 and loses points per problem. It ranks rows for checking; it is not a probability.
* Each run writes `campaigns/<name>/quality-<list>-<date>.md`: coverage per field, email statuses, issue counts and the ten lowest-confidence rows.

### Paid mailbox checks

Set the key in your own terminal, never in the repo: `export ZEROBOUNCE_API_KEY=...` or `export NEVERBOUNCE_API_KEY=...`. Then
`campaign enrich nj-dental --verifier zerobounce --max-verifications 50`. Results are cached in `.leadengine/verify_<name>.json`,
so an address is never billed twice. Check the provider's current price before a large run.

### Google Places data

Places answers (has a website, has a Google profile, review count) are cached for 30 days and then fetched again, because Google's terms limit
how long Places content may be stored. Use Places-derived fields for your own outreach. Do not sell or hand over lists built from them
without reading the Google Maps Platform terms first (see docs/COMMERCIAL_REVIEW.md).
