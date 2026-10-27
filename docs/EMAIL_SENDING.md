# Sending email in batches

The engine can send marketing emails to the contacts it found, but only in small batches that you have read and approved,
from your own mailbox, at a pace that protects your sending reputation. Everything runs on your own computer. No keys or passwords go in the repo.

## How a mailing works

```
python3 -m leadengine campaign mail plan    nj-dental nov-intro --template examples/mail_template_example.txt
python3 -m leadengine campaign mail preview nj-dental nov-intro --batch 1        # read campaigns/nj-dental/mail/nov-intro/batch-01.md
python3 -m leadengine campaign mail approve nj-dental nov-intro --batch 1 --hash <hash from the preview>
python3 -m leadengine campaign mail send    nj-dental nov-intro --batch 1 --dry-run   # writes the emails to a folder, sends nothing
python3 -m leadengine campaign mail test    nj-dental nov-intro --to you@yourdomain.com   # one sample to your own address
python3 -m leadengine campaign mail send    nj-dental nov-intro --batch 1        # asks you to type SEND, then sends
python3 -m leadengine campaign mail sync    nj-dental                            # pulls replies, opt-outs and bounces back in
python3 -m leadengine campaign mail status  nj-dental
```

1. **Plan** picks recipients from `approved.csv` (the leads you kept at review), or from `--list FILE`, and splits them into batches.
   Everyone it leaves out is in `excluded.csv` with the reason.
2. **Preview** is the dry run you read: the count, today's cap, the send window, every recipient, and rendered samples with the exact
   From, To, Subject and unsubscribe headers. It ends with a hash.
3. **Approve** with that hash. If anything changed after you read it (the template, the sender details or the recipients), the hash no longer matches and approval is refused.
4. **Send** sends only the approved addresses, with exactly the approved content. It checks each person again just before their email:
   anyone who opted out, replied or bounced since you approved is skipped. It refuses to run without a person at the keyboard unless you add `--yes`.
5. **Sync** reads replies and bounce notices from your mailbox. "No thanks", "unsubscribe" and "remove me" become opt-outs. Any real reply
   stops future mailings and planned follow-ups to that person. Out-of-office replies are ignored.

The first emails of an outreach sequence can go out the same way: `campaign batch preview` then `batch approve --hash`, then `campaign batch send <name> DATE`.

### Template

```
Subject: A faster website for {company}

Hi {first_name},
...
{sender_name}
```
Merge fields: `{first_name}` (reads "there" when unknown), `{last_name}`, `{company}`, `{city}`, `{state}`, `{website}`, `{title}`,
`{sender_name}`, `{business_name}`, `{portfolio_url}`, `{booking_link}`. Anyone missing a field the template uses is left out instead of getting a gap.
Every email gets this footer automatically: your name and business, your postal address, a line saying it is a marketing email, and how to opt out.

## Who never gets an email

- anyone in `suppress.csv` (opt-outs, bounces, do-not-contact), by address, domain or company
- anyone who replied, booked, filled a form, opted out or bounced (from `events.csv`)
- anyone already sent this mailing, or emailed from your address in the last 30 days (`mail.min_days_between`)
- anyone still in an active outreach sequence
- addresses whose status is not Valid or Risky. Contacts found on websites are Risky. Run a verifier before trusting Unverified ones.
- a second person at the same business domain in one mailing. Free mail like gmail.com is not grouped.
- addresses from a website that says its addresses are not for commercial email. The contact finder now keeps none from such sites.

## Limits (campaigns/<name>/config.json, "mail" block)

| Setting | Default | What it does |
|---|---|---|
| `batch_size` | 10 | emails per approved batch |
| `daily_cap` | 30 | most emails per day from your address, across all campaigns |
| `warmup` | `[[7, 10], [14, 20]]` | a new sending address: 10 a day in week 1, 20 in week 2, then `daily_cap` |
| `delay_seconds` | `[60, 180]` | random pause between emails |
| send window | Mon-Fri 09:30-11:30 | from the spec's `outreach.send_window`, in `mail.timezone` (default America/New_York). `--wait` waits for it to open |
| `max_failures` | 3 | stop the batch after 3 failures |
| `bounce_limit` | 0.05 | stop sending when more than 5% of the last 30 days' emails bounced (with at least 20 sent) |

Raise them slowly. Gmail allows about 500 a day on a personal account and 2,000 on Google Workspace. Cold email that gets ignored or marked as spam
hurts your domain long before you reach those numbers.

## Set up your sender (once)

Fill in `campaigns/<name>/config.json`:
```json
{
  "sender": {"name": "Your Name", "business": "AYiN Advisors", "address": "street, city, state ZIP (a real postal address or a PO box)",
             "reply_email": "you@yourdomain.com", "offer": "..."},
  "mail": {"provider": "smtp", "from_email": "you@yourdomain.com"}
}
```
Send from your own domain on Google Workspace or another business mailbox rather than a personal @gmail.com, and make sure the domain has
SPF, DKIM and DMARC records (Workspace: Admin console > Apps > Gmail > Authenticate email; the records are in [SETUP.md](SETUP.md) section 4).
Without them, mail lands in spam.

### Option A: SMTP with an app password (simplest)

Works with Gmail and Google Workspace, Outlook, Zoho, and relays like Amazon SES or SendGrid's SMTP.

1. Gmail or Workspace: turn on 2-Step Verification, then go to myaccount.google.com > Security > App passwords and create one named "lead engine".
   (Workspace admins may need to allow app passwords.)
2. In the terminal on your computer, not in a chat or a file in the repo:
   ```
   export LEADENGINE_SMTP_HOST=smtp.gmail.com
   export LEADENGINE_SMTP_USER=you@yourdomain.com
   export LEADENGINE_SMTP_PASSWORD='the 16-character app password'
   ```
   Port 587 with STARTTLS is the default. Set `LEADENGINE_SMTP_PORT=465` for SSL. Or put the same keys (`host`, `user`, `password`, `port`, `security`)
   in `~/.config/leadengine/smtp.json` and run `chmod 600` on it.
3. Check the login without sending anything: `python3 -m leadengine mail check smtp`.
4. For `mail sync` over IMAP, also set `LEADENGINE_IMAP_HOST=imap.gmail.com`. The user and password default to the SMTP ones.

### Option B: the Gmail API (no password stored)

1. console.cloud.google.com > create a project > APIs & Services > Library > enable the **Gmail API**.
2. OAuth consent screen: User type External (or Internal on Workspace), app name "lead engine", add yourself as a test user.
3. Credentials > Create credentials > OAuth client ID > **Desktop app** > download the JSON and save it as `~/.config/leadengine/gmail-client.json`.
4. Run `python3 -m leadengine mail auth gmail --read` and approve in the browser. `--read` also lets `mail sync` read replies.
   The token is saved to `~/.config/leadengine/gmail-token.json`, readable only by you.
5. Set `"provider": "gmail"` in the mail block. `from_email` must be the Gmail address you signed in with.

While the app stays in Testing mode, Google expires the sign-in after 7 days. Run step 4 again when `send` says the authorisation expired.
The Gmail API itself is free.

### Later: Amazon SES, SendGrid, Postmark

Their SMTP relays work today through Option A (host, user and password from their console). A native HTTP API provider is a small class
with `account()` and `send(msg)` registered through `mailer.register("ses", ...)`. These services are paid beyond their free tiers, so they wait for your decision.

## The rules this follows (CAN-SPAM)

- accurate From and Reply-To: your name and your address. Gmail refuses a From that is not the signed-in account.
- honest subjects: `Re:` and `Fwd:` on a first email, "invoice", "final notice", all capitals and the like are refused
- it says it is a marketing email, and it includes your physical postal address
- a working opt-out in every email (reply "no thanks", or email the unsubscribe address), plus a `List-Unsubscribe` header.
  Run `mail sync` (or `events import`) at least weekly so opt-outs are honoured well within the law's 10 business days.
- no addresses kept from sites that say not to collect them

Healthcare practices are businesses here, so this is B2B marketing email. Never put patient information in a template or a list.
