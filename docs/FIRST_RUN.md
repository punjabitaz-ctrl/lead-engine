# First run on your computer

About 15 minutes for steps 1 to 3. Nothing here emails anyone or costs money. Steps 1 to 3 need no accounts, keys or passwords.

## 1. Get the code (once)

Needs Python 3.9 or newer and git. In a terminal:

```
git clone https://github.com/punjabitaz-ctrl/lead-engine.git
cd lead-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[sheets]"
```
On Windows, the fourth line is `.venv\Scripts\activate`. In a new terminal later: `cd lead-engine` and the `activate` line again.
Run every command below from the `lead-engine` folder.

## 2. See it work on sample data (optional, 1 minute)

```
python3 -m leadengine first-run --demo
```
It runs every step on made-up practices without the internet, so you can see what the real run prints and writes.
Delete `campaigns/demo-nj-medical/` afterwards.

## 3. The real first run

```
python3 -m leadengine first-run
```
That one command:
1. checks your computer can reach the NPI Registry (free, run by CMS) and Google's DNS service
2. creates the campaign `campaigns/nj-medical/`: NJ, Middlesex County, cardiology and ophthalmology practices (the focus tier)
3. finds up to 25 privately owned practices, leaving out hospital systems and national chains
4. checks each one (phone rules, NPI active in the registry, duplicates) and writes a quality report
5. saves a spreadsheet, `campaigns/nj-medical/exports/nj-medical-first-run.xlsx`
6. says whether your sender details are ready for email (they won't be yet; that is step 4)

It makes many small registry queries, so give it a few minutes. Lines like `[nppes] 0 results for ...` are normal for small towns.
A line for a whole specialty with 0 results everywhere means a search term needs fixing: send me that line.

Other places or sizes: `--county Somerset`, `--county Middlesex --county Somerset`, `--target 50`. Running it again adds the next batch
to the same campaign; leads already found are not repeated.

Then review: open `campaigns/nj-medical/review/pack-01.csv`, put Keep, Drop or Unsure in the Decision column, save, and run
```
python3 -m leadengine campaign approve nj-medical campaigns/nj-medical/review/pack-01.csv
```

**What to expect.** Registry leads come with the practice name, the owner or official on file, a phone number and an address. They do not
come with a website or an email address. So this first list is for calls, letters or visits. For email you need websites first: a Google Places key
(paid beyond Google's free monthly allowance; docs/SETUP.md section 2) or your own list (`campaign run nj-medical --manual FILE.csv`). Tell me which
and I'll set it up.

## 4. Sender details and mailbox (only when you are ready to email)

### 4a. Decide the address you send from
Use a mailbox on the domain you sell from, ideally a subdomain set aside for outreach, with SPF, DKIM and DMARC records. A new address starts slow:
the engine sends 10 a day in week 1 and 20 in week 2. Details: [EMAIL_SENDING.md](EMAIL_SENDING.md) and [SETUP.md](SETUP.md) section 4.

### 4b. Your details, once
```
cp examples/sender_config_example.json ~/leadengine-sender.json
```
Open `~/leadengine-sender.json`, replace every `[bracket]`, save. CAN-SPAM needs a real postal address (a PO box works). Then:
```
python3 -m leadengine first-run --sender ~/leadengine-sender.json
```
It copies the details into the campaign and prints `Sender details for email: ready.` or what is still missing. Anything left in brackets is not copied.
The file sits outside the repo, so your details never get committed.

### 4c. Mailbox login (Gmail or Google Workspace with an app password)
Turn on 2-Step Verification, then create an app password at myaccount.google.com > Security > App passwords. Type these in your terminal,
not in a file in the repo and not in a chat:
```
export LEADENGINE_SMTP_HOST=smtp.gmail.com
export LEADENGINE_SMTP_USER=you@yourdomain.com
export LEADENGINE_SMTP_PASSWORD='the 16-character app password'
python3 -m leadengine mail check smtp
```
`mail check` logs in and sends nothing. The Gmail API, which stores no password, is in EMAIL_SENDING.md option B.

### 4d. A dry run, then a test to yourself
Once `approved.csv` has leads with emails:
```
python3 -m leadengine campaign mail plan nj-medical intro --template examples/mail_template_example.txt
python3 -m leadengine campaign mail preview nj-medical intro --batch 1
python3 -m leadengine campaign mail approve nj-medical intro --batch 1 --hash <the hash preview printed>
python3 -m leadengine campaign mail send nj-medical intro --batch 1 --dry-run
python3 -m leadengine campaign mail test nj-medical intro --to you@yourdomain.com
```
The dry run writes the emails to a folder. `mail test` sends one sample to your own address. The real send
(`mail send` without `--dry-run`, where you type SEND) is yours to run when you choose.

## What has only been tested with stand-ins

Everything that touches the internet was written to each service's documentation and tested with stand-ins: NPI Registry search and
lookups, DNS email checks, website checks, SMTP and Gmail sending, reading replies. Your first run is the first time they meet the real services.
If something fails, copy the last 20 lines it printed and send them to me.
