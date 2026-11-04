# Phase 1 Execution — Launch Ready (Weeks 1-2)

**Goal:** Get to launch-ready state with a working sending domain, live landing page, first campaign run, and sales materials.

**Total Estimate:** ~28 hours across 6 items

---

## Status Dashboard

| # | Task | Est. Hours | Status | Notes |
|---|------|------------|--------|-------|
| 1 | Set up sending domain + DNS | 4 | ⏳ Not Started | Purchase subdomain, configure SPF/DKIM/DMARC |
| 2 | Build landing page (AYiN offer) | 8 | ✅ **COMPLETE** | [examples/lead-engine-landing.html](../examples/lead-engine-landing.html) created |
| 3 | Run first live NJ medical campaign | 6 | ⏳ Not Started | `leadengine doctor`, then `campaign init/run` |
| 4 | Create sales one-pager | 4 | ⏳ Not Started | One-page PDF with offer, pricing, process |
| 5 | Set up support email | 2 | ⏳ Not Started | Dedicated support address, forwarding rules |
| 6 | Legal review of email templates | 4 | ⏳ Not Started | CAN-SPAM compliance check |

---

## Completed Items

### ✅ Item 2: Landing Page
**File:** `examples/lead-engine-landing.html`
- Matches AYiN Advisors design style
- Three practice models clearly defined
- How-it-works section with 4-step process
- Values section (Evidence over theory, Candid counsel, Sequenced)
- CTA to book consultation
- Mobile responsive

---

## Remaining Phase 1 Items

### ⏳ Item 1: Set up sending domain + DNS (4 hours)
**Priority:** CRITICAL — Without this, emails go to spam or bounce.

**Deliverables:**
- Purchase subdomain (e.g., `leads.ayin.momento.family`)
- Configure DNS records:
  - SPF record
  - DKIM record  
  - DMARC policy
- Set up warm-up mailbox
- Test with Gmail API or SMTP provider

**Next Step:** Purchase domain and configure DNS.

---

### ⏳ Item 3: Run first live NJ medical campaign (6 hours)
**Priority:** HIGH — Need proof of concept before marketing.

**Deliverables:**
- `leadengine doctor` — verify network access
- `campaign init nj-dental --state NJ --county Middlesex --vertical healthcare-practices`
- `campaign run nj-dental` — discover stage (59 leads)
- Export and review first pack
- Document results: coverage rate, email availability, NPI status

**Next Step:** Run `leadengine doctor` to check network.

---

### ⏳ Item 4: Create sales one-pager (4 hours)
**Priority:** HIGH — Need this for outreach conversations.

**Deliverables:**
- One-page PDF with:
  - Problem statement (practices without websites/leads)
  - Solution overview
  - Three pricing tiers (from `offer.json`)
  - Process timeline
  - Social proof placeholders
  - CTA to book call

**Next Step:** Draft content in Google Docs or Markdown.

---

### ⏳ Item 5: Set up support email (2 hours)
**Priority:** MEDIUM — Needed for customer inquiries.

**Deliverables:**
- Dedicated address: `support@ayin.momento.family` or similar
- Forwarding rules set up
- Auto-responder draft
- Ticket template for tracking

**Next Step:** Create email account and configure forwarding.

---

### ⏳ Item 6: Legal review of email templates (4 hours)
**Priority:** HIGH — Compliance before sending.

**Deliverables:**
- Review all email templates in `examples/mail_template_example.txt`
- Add CAN-SPAM required elements:
  - Clear subject line (no deception)
  - Valid physical address
  - Clear opt-out mechanism
  - Identify who sent it
- Document legal review date and reviewer

**Next Step:** Pull template, add missing elements.

---

## Execution Order

1. **Item 2** ✅ Landing page (DONE)
2. **Item 1** Sending domain setup
3. **Item 6** Legal review of templates (can run in parallel with #1)
4. **Item 5** Support email setup
5. **Item 3** First live campaign run
6. **Item 4** Sales one-pager (after seeing campaign results)

---

## Quick Start Commands

```bash
# Check network access
python3 -m leadengine doctor

# Initialize a campaign
python3 -m leadengine campaign init nj-dental --state NJ --county Middlesex --vertical healthcare-practices

# Run discover stage (59 leads)
python3 -m leadengine campaign run nj-dental

# Check status
python3 -m leadengine campaign status nj-dental --json
```

---

## Files to Update

- [x] `examples/lead-engine-landing.html` — Created
- [ ] `templates/email_template_canspam.txt` — Add physical address, opt-out link
- [ ] `sales/sales_onepager.md` — Draft content
- [ ] `support/support_email_setup.md` — Documentation
- [ ] `.env` or config for sending domain credentials

---

**Last Updated:** 2026-11-03
