# Lead tracker (small, Supabase)

Logs when a lead clicks your link or visits your site so the sheet can score **Interest Level**.

## What gets stored

One row per event: time, lead key (the sheet's Dedupe Key, e.g. `earthcam.net` or `garden state family care|newark`), event type,
page path, user-agent, and a bot flag. **No IP address and no cookies.** The lead key can contain a practice or person's name, so
treat the table as personal data and disclose the tracking in your privacy policy.

## Link modes (Config row 109 on the sheet)

| Mode | Link in the email | Tracks | Trade-off |
|---|---|---|---|
| `plain` | your portfolio URL | nothing | best deliverability |
| `utm` | your URL + `utm_source=leadengine&utm_content=<key>` | visits and form fills, via `track.js` on your site | **recommended**: no third-party domain in the link |
| `redirect` | `<tracker>/t?l=<key>&to=<your URL>` | clicks, then visits | link points at `*.supabase.co` until you add a custom domain |

## Deploy

1. Run `migration.sql` on the project (table `lead_events`, RLS on, no public policies).
2. Deploy `index.ts` + `lib.ts` as an edge function named `lead-tracker` with **JWT verification off**.
3. Secrets: `ALLOWED_HOSTS` (e.g. `tazabbas.com,momento.family`; only these hosts can be redirect targets or send beacons) and
   `EXPORT_TOKEN` (a long random string).
4. Sheet: Config B108 = `https://<project>.supabase.co/functions/v1/lead-tracker`, B109 = `utm` or `redirect`.
5. Sites: paste `track.js` before `</body>` (edit `ENDPOINT`).
6. Apps Script: add properties `TRACKER_URL` and `EXPORT_TOKEN`, then **Lead Engine > Pull clicks and visits**.

## Honest limits

- Security scanners and link previewers click links. Known ones are flagged and excluded from the export; unknown ones will
  slip through, so a click alone scores only 5 points and one event per lead per day is counted.
- Anyone can POST fake events for a lead key they know. Origin checks stop casual abuse, not a determined one.
- No rate limiting is built in.
- The function was unit-tested for its helpers only (`node --test tracker/lib.test.ts`); it has not run on Supabase yet.
