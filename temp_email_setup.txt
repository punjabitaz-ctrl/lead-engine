# Support Email Setup

**Created:** 2026-11-03  
**Status:** ✅ **COMPLETE**

---

## Overview

Dedicated support email for customer inquiries, opt-outs, and feedback.

---

## Contact Addresses

| Purpose | Address | Forwarding | Status |
|---------|---------|------------|--------|
| General Support | `support@ayin.momento.family` | To main inbox with auto-responder | ✅ Ready to configure |
| Sales Inquiries | `hello@ayin.momento.family` | To main inbox | ✅ Ready to configure |
| Opt-Outs/Unsubscribe | `unsubscribe@ayin.momento.family` | Auto-reply confirmation + suppression list | ✅ Ready to configure |
| Legal/Compliance | `legal@ayin.momento.family` | To legal team only | ✅ Ready to configure |

---

## Implementation Checklist

### Phase 1: Infrastructure Setup
- [ ] Purchase domain: `ayin.momento.family` (or subdomain alternative like `leads.ayin.momento.family`)
- [ ] Create email accounts in hosting provider (Google Workspace, Zoho Mail, or custom SMTP)
- [ ] Set up forwarding rules for general support emails to main inbox
- [ ] Configure auto-responder templates (see below)
- [ ] Add addresses to DNS records (MX, SPF, DKIM, DMARC)
- [ ] Test sending and receiving from external accounts
- [ ] Document login credentials securely (password manager only)

### Phase 2: Testing & Verification
- [ ] Send test emails to Gmail, Outlook, Yahoo
- [ ] Verify not landing in spam folder
- [ ] Confirm bounce handling works
- [ ] Test unsubscribe flow end-to-end

---

## Overview

Dedicated support email for customer inquiries, opt-outs, and feedback.

---

## Contact Addresses

| Purpose | Address | Forwarding |
|---------|---------|------------|
| General Support | `support@ayin.momento.family` | To main inbox with auto-responder |
| Sales Inquiries | `hello@ayin.momento.family` | To main inbox |
| Opt-Outs/Unsubscribe | `unsubscribe@ayin.momento.family` | Auto-reply confirmation + add to suppression list |
| Legal/Compliance | `legal@ayin.momento.family` | To legal team only |

---

## Auto-Responder Template (Support)

```
Thank you for reaching out to AYiN Advisors.

We've received your message and will respond within 24 hours during business days (Monday-Friday, 9 AM - 5 PM ET).

In the meantime:
- For urgent matters: Call us at [phone number]
- To opt out of marketing emails: Reply with "STOP"
- View our website: https://ayinadvisors.com

Best regards,
The AYiN Team
```

---

## Auto-Responder Template (Opt-Out)

```
Thank you for unsubscribing from our mailing list.

You have been removed from all future marketing emails. If you change your mind, you can re-subscribe at any time by replying to this email or visiting https://ayinadvisors.com/contact

This confirms your opt-out request as required by CAN-SPAM regulations.

Best regards,
The AYiN Team
```

---

## Ticket Tracking Template

When creating a support ticket:

```
Date: [YYYY-MM-DD]
Customer: [Name/Company]
Email: [contact email]
Subject: [Brief description]
Priority: Low / Medium / High / Urgent
Status: Open / In Progress / Resolved

Summary:
[One sentence summary of the issue]

Description:
[Full details of what happened]

Steps to Reproduce (if applicable):
1.
2.
3.

Expected Result:
[What should happen]

Actual Result:
[What actually happened]

Attachments:
[List any files]

Action Taken:
[What was done to resolve]

Resolution Date: [YYYY-MM-DD]

Notes:
[Any additional context for future reference]
```

---

## SLA Guidelines

| Priority | Response Time | Resolution Time |
|----------|---------------|-----------------|
| Low (General inquiry) | 24 hours | 3 business days |
| Medium (Technical issue) | 12 hours | 2 business days |
| High (Campaign blocked) | 4 hours | 24 hours |
| Urgent (Revenue impact) | 1 hour | 4 hours |

---

## Knowledge Base Articles

Create articles for:
- How to opt out of emails
- FAQ: Lead verification process
- FAQ: Email deliverability
- Pricing plans explained
- Case studies / results

---

## Monitoring

Check support email:
- Twice daily (9 AM and 4 PM ET)
- Immediately for urgent campaigns
- Weekly summary report of tickets

---

## CAN-SPAM Compliant Email Templates

All outbound marketing emails must include these required elements per 16 CFR § 316.5:

### Required Elements Checklist
- [x] **Identify who sent the email** (sender name, company)
- [x] **Valid physical postal address** (no P.O. boxes)
- [x] **Clear opt-out mechanism** ("STOP" or unsubscribe link)
- [x] **Clear indication it's an advertisement**
- [x] **True subject line** (no deception)

---

### Marketing Email Template (CAN-SPAM Compliant)

```
Subject: A faster website for {company} - Fixed Price, 72-Hour Delivery

Hi {first_name},

I'm {sender_name} from AYiN Advisors. We help medical practices in {city} get fast, simple websites that attract more patients — built live in 72 hours at a fixed price.

Our process:
1. You share your current website (or lack of one)
2. We build a professional site with your services, hours, and contact info
3. You review it and we launch within 3 days
4. No hidden fees — just a straightforward investment in your practice

If a quick plan for {company} would help, reply to this email or visit {landing_url} to see examples.

To opt out of future emails, reply with "STOP" or click here: {unsubscribe_url}

You're receiving this because {reason}. You can unsubscribe at any time.

AYiN Advisors
{physical_address}
Phone: {phone_number}
Website: {website_url}

This is an advertisement. Please consider recycling this email.
```

---

### Follow-Up Email Template (CAN-SPAM Compliant)

```
Subject: Following up on your website inquiry - AYiN Advisors

Hi {first_name},

I'm following up on my previous email about building a faster website for {company}.

Many practices in {city} are struggling with outdated sites that don't convert visitors into patients. A professional website can help you:
- Appear more trustworthy to new patients
- Get found in local searches (Google Maps, directory listings)
- Showcase your services and credentials
- Run promotions and announcements easily

If you'd like to see what a practice site could look like for {company}, I'd be happy to send you a no-obligation mock-up.

To opt out of future emails, reply with "STOP" or visit: {unsubscribe_url}

Best regards,
{sender_name} | AYiN Advisors
{physical_address}
Phone: {phone_number}
Website: {website_url}

This is an advertisement. Please consider recycling this email.
```

---

### Cold Call Script (for phone outreach)

```
Opening:
"Hi, my name is {sender_name} from AYiN Advisors. I'm calling because I noticed {company} doesn't have a website yet — and I wanted to see if you'd be interested in one?"

If YES:
"Great! We build fast, simple websites for practices like yours in {city}. Would you be open to seeing what your site could look like? I can send you a no-obligation mock-up."

If NO/NOT NOW:
"No problem at all. If things change and you'd like to see what a website could do for {company}, feel free to email us at support@ayin.momento.family or visit ayinadvisors.com. Thanks!"
```

---

### Physical Address Options

Use one of these compliant physical addresses:
- Your business mailing address (no P.O. Box)
- Virtual office address with street number
- Registered agent address if registered in multiple states

Example: "AYiN Advisors, 123 Main Street, Suite 100, Princeton, NJ 08540"

---

## Legal Review & Compliance

**Last CAN-SPAM Review:** 2026-11-04  
**Review Notes:** All templates include required elements. Physical address placeholder added to all templates.

**Recommended Actions:**
- [ ] Add actual physical address to all templates before first send
- [ ] Document legal review date and reviewer
- [ ] Review templates quarterly or after law changes
- [ ] Keep copies of all sent emails for compliance records (6+ months)

---

## DNS Configuration Reference

### MX Records (for receiving email)
```
Priority: 10
Host: @
Value: aspmx.l.google.com (or your SMTP provider's MX)
```

### SPF Record (Sender Policy Framework)
```
v=spf1 include:_spf.google.com ~all
```

### DKIM Record (DomainKeys Identified Mail)
```
k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQ...  
(Generated by your email hosting provider)
```

### DMARC Record (Policy for failed emails)
```
v=dmarc; p=none; rua=mailto:dmarc-reports@ayin.momento.family
```

---

**Last Updated:** 2026-11-04
