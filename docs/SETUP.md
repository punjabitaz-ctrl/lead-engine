# Setup checklist

Four things only you can do (they need your accounts or DNS). Never paste a key into chat: store it as an environment
variable in the cloud environment (menu in the session title bar, then Edit). A new session picks it up.

## 1. Let the sandbox reach the registry and Google

Only you can do this (it is an environment setting, not something the assistant can change). Afterwards start a **new session** and run
`python3 -m leadengine doctor` to confirm. As of 2026-10-09 only `places.googleapis.com` was reachable; everything else below was blocked.

The environment's network policy blocks hosts it has not been told about. In **Edit environment > Network access**, choose a
broader level, or add these under **Allowed domains**:

- `npiregistry.cms.hhs.gov` (NJ provider data, free, no key)
- `places.googleapis.com` (presence checks)
- `api.adzuna.com` (optional job signals)
- `tazabbas.com` (optional; lets the tool audit and read your portfolio)
- `data.cms.gov`, `www.cms.gov`, `download.medicaid.gov` (public Medicare spending, NADAC drug costs; see `docs/specialty_rubric.md`)
- `www2.census.gov` (official municipality lists, used to load the remaining NJ counties)
- `mzsrtwrbpdpehthwmkwt.supabase.co` (only to smoke-test the live tracker)

Steps: https://code.claude.com/docs/en/cloud-environments#network-access

For the Middlesex/Somerset hospital price files add `rwjbh.org`, `saintpetershcs.com`, `hackensackmeridianhealth.org`, `www1.pennmedicine.org`
(registry: `leadengine/data/hospital_mrf_registry.csv`). Other hospitals' files live on their own websites, so they cannot be allow-listed one by one. Either raise the access level
temporarily while they are collected, or download the files yourself and put them in the repo or Google Drive.

## 2. Google Places key (presence checks run automatically)

1. Google Cloud Console > create a project > attach billing (a card is required even for the free allowance).
2. APIs & Services > Library > enable **Places API (New)**.
3. APIs & Services > Credentials > Create credentials > API key. Click **Restrict key** > API restrictions > **Places API (New)** only.
4. **Cap the spend at Google, not only in the tool:** APIs & Services > Places API (New) > Quotas > set a daily request limit
   (suggest 100/day while testing). Billing > Budgets & alerts > create a budget of $25 with alerts at 50/90/100%.
5. Add the key to the environment as `GOOGLE_PLACES_API_KEY`.

Cost: Google's published table lists Text Search *Enterprise* (the tier that returns website and phone) at about $35 per 1,000
requests with 1,000 free per month. I could not confirm the effective date, so check the live pricing page before relying on it.
The tool enforces its own caps on top: `--max-places-calls` (default 200 per run) and `--monthly-places-cap` (default 1,000),
caches every answer on disk so a business is never looked up twice, and prints the running cost estimate after each batch.

```
python3 -m leadengine run --source nppes --state NJ --tier 1 --presence-check places
```

## 3. Click and visit tracker (Supabase)

Deployed to project `lead-engine-tracker` (`mzsrtwrbpdpehthwmkwt`, free plan). Two secrets still need your hand: see `tracker/README.md`.

## 4. Sending from momento.family

Sending volume is limited by reputation, not by tools. A new setup that starts large gets blocked.

- **Use a subdomain, not the root.** For example `mail.<your-domain>`, with its own mailbox. Send from **`mail.momento.family`**. You also own `memento.family` (the likely typo domain): park it, publishing `v=spf1 -all` (TXT on the root) and a DMARC record `v=DMARC1; p=reject` so nobody can spoof it, and redirect its web address to `momento.family`. Mailbox provider is not decided yet; the SPF/DKIM values depend on it. A flagged sending domain then does not
  damage the root domain you use for real family email.
- **Authenticate it.** At your DNS provider add (placeholders in angle brackets, the exact values come from your mail provider):
  - SPF: TXT on the subdomain, `v=spf1 include:<your provider's SPF include> ~all`
  - DKIM: the TXT/CNAME record your provider generates for the subdomain
  - DMARC: TXT at `_dmarc.<subdomain>`, start with `v=DMARC1; p=none; rua=mailto:<you>@<domain>`, move to `p=quarantine` after two clean weeks
- **Warm up.** About 10-20 emails a day per mailbox in week 1, 25-30 in week 2, 40 in week 3, 50 in week 4, only to verified
  addresses, with real replies where possible. Add mailboxes rather than pushing one past those numbers.
- **Rules that apply at scale.** Gmail and Yahoo have required SPF, DKIM, DMARC, one-click unsubscribe and a spam-complaint rate
  under 0.3% for bulk senders (about 5,000 a day to their users) since 2024. Verify the current thresholds. CAN-SPAM applies at any
  volume: honest headers, a postal address, a working opt-out honoured within 10 business days.
- **Match the identity.** A family-branded domain emailing medical offices, with links to a different domain, looks off to people
  and to spam filters. Prefer a sending domain that matches what you sell, or make the From name, signature and link domain agree.
- **Links.** Redirect-tracked links route through a third-party domain, which can hurt deliverability. Link mode `utm` (your own
  URL plus tags, with `tracker/track.js` on your site) avoids that and is the recommended default once the tracker is live.
- **Reality check for the NJ medical segment.** Practices with no web presence mostly have no email address. Expect phone,
  postcard and walk-in to be the main channels; email volume will be small.
