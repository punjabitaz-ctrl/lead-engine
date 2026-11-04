# Sending Domain Setup

**Created:** 2026-11-03  
**Status:** Pending implementation  
**Priority:** Phase 1 - Highest

---

## Overview

Dedicated sending domain for email campaigns to ensure deliverability and protect main domain reputation.

---

## Domain Requirements

| Requirement | Details |
|-------------|---------|
| Subdomain | `ayin.momento.family` (or similar) |
| DNS Management | Full access needed |
| MX Records | Point to Gmail/SMTP provider |
| SPF/DKIM/DMARC | All three required |
| Warm-up Period | 14 days minimum before scaling |

---

## Step 1: Domain Registration/Purchase

### Option A: Existing Domain
- If you own `ayinadvisors.com`, create subdomain `sending.ayinadvisors.com`
- Configure DNS at your current registrar (GoDaddy, Namecheap, etc.)

### Option B: New Domain Purchase
- Recommended: Google Domains, Namecheap, or Cloudflare
- Cost: ~$10-15/year
- Purchase: `ayin.momento.family` or similar

**Action:** [ ] Confirm domain choice and purchase if new

---

## Step 2: DNS Configuration

### A Record (if using Gmail SMTP)
```
Type: A
Name: ayin
Value: 142.250.185.78 (or current Gmail IP range)
TTL: 3600
```

### MX Record (for incoming mail)
```
Type: MX
Name: @
Priority: 10
Value: SMTP.google.com
```

---

## Step 3: SPF Record (Sender Policy Framework)

```
Type: TXT
Name: ayin
Value: v=spf1 include:_spf.google.com ~all
TTL: 3600
```

**Note:** Add all SMTP providers used. Maximum 10 TXT records.

---

## Step 4: DKIM (DomainKeys Identified Mail)

### For Gmail:
1. Go to Google Admin Console → Apps → Gmail → Authenticate email
2. Generate DKIM key
3. Add CNAME record provided by Google

**Alternative:** Use a dedicated SMTP service that handles DKIM automatically

---

## Step 5: DMARC Record (Domain-based Message Authentication)

### Phase 1 - Monitoring (Weeks 1-2)
```
Type: TXT
Name: _dmarc.ayin.momento.family
Value: v=DMARC1; p=none; rua=mailto:dmarc-reports@ayin.momento.family
```

### Phase 2 - Quarantine (Weeks 3-4)
```
Type: TXT
Name: _dmarc.ayin.momento.family
Value: v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@ayin.momento.family
```

### Phase 3 - Enforcing (After 4 weeks of good metrics)
```
Type: TXT
Name: _dmarc.ayin.momento.family
Value: v=DMARC1; p=reject; rua=mailto:dmarc-reports@ayin.momento.family
```

---

## Step 6: Email Verification Service Setup

### ZeroBounce / NeverBounce Integration

**Required:** API key and budget allocation

| Provider | Cost | Features |
|----------|------|----------|
| ZeroBounce | $49-199/month | Real-time verification, spam checks |
| NeverBounce | $49-299/month | High deliverability, detailed reports |
| NeverVerify | $39-149/month | Budget-friendly option |

**Action:** [ ] Select provider and purchase plan  
**Action:** [ ] Generate API key and add to `config.json`

---

## Step 7: Warm-up Schedule

### Days 1-3: Very Light
- Send: 10-20 emails/day
- Mix: Personal + campaign emails
- Time: Same time each day

### Days 4-7: Light
- Send: 25-50 emails/day
- Focus: Engaged recipients only

### Days 8-14: Moderate
- Send: 50-100 emails/day
- Monitor bounce rate (<2% target)

### Day 15+: Normal Operations
- Send: Up to 200/day (Gmail default limit)
- Full campaign volume

---

## Step 8: Testing Checklist

Before first campaign:

- [ ] SPF record propagates (check with MXToolbox)
- [ ] DKIM signature valid
- [ ] DMARC configured for monitoring
- [ ] Send test email to Gmail, Outlook, Yahoo
- [ ] Check spam folder placement
- [ ] Verify domain reputation (Google Postmaster Tools)

---

## Monitoring Tools

### Free Tools
- **MXToolbox.com** - DNS record verification
- **Google Postmaster Tools** - Domain reputation metrics
- **Mail-Tester.com** - Email quality check

### Paid Tools (Optional)
- **SenderScore.org** - Industry reputation score
- **GlockApps** - Deliverability testing

---

## Troubleshooting

### Emails going to spam:
1. Check SPF/DKIM alignment
2. Review DMARC policy level
3. Test with Mail-Tester.com
4. Reduce sending volume temporarily
5. Remove hard bounces immediately

### High bounce rate (>5%):
1. Verify email list quality
2. Run through verification service
3. Segment and clean inactive addresses
4. Consider smaller batch sizes

---

## Security Checklist

- [ ] Change default admin passwords on domain registrar
- [ ] Enable 2FA on all accounts
- [ ] Use app-specific password for SMTP (not main account)
- [ ] Never commit API keys to git
- [ ] Rotate credentials quarterly

---

**Last Updated:** 2026-11-03  
**Next Review:** After first campaign launch
