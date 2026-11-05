EMAIL INFRASTRUCTURE SETUP - PRODUCTION READY
======================================================================
Created: 2026-11-04
Status: Step 1 of GTM Launch

STEP 1: DOMAIN & DNS CONFIGURATION
===================================

RECOMMENDED SETUP (Choose ONE option):

OPTION A - Google Workspace (Recommended for B2B outreach)
-----------------------------------------------------------
Domain: leads.momento.family or sends.ayinadvisors.com

1. PURCHASE DOMAIN ($10-15/year)
   - Go to Namecheap.com or Cloudflare.com
   - Purchase subdomain: mail.yourdomain.com

2. CREATE GOOGLE WORKSPACE ACCOUNT
   - Go to workspace.google.com
   - Sign up for Business Starter ($6/user/month)
   - Create user: outreach@leads.momento.family
   
3. CONFIGURE SPF RECORD (TXT record at root domain)
   
   Type: TXT
   Name/Host: @
   Value: v=spf1 include:_spf.google.com ~all
   
4. ENABLE DKIM IN GOOGLE ADMIN CONSOLE
   - Admin Console -> Apps -> Google Workspace -> Gmail -> Advanced settings
   - Enable DKIM, copy the key
   - Add as TXT record:
   
   Type: TXT  
   Name/Host: mail._domainkey
   Value: v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQ...

5. CONFIGURE DMARC (Start with monitoring)
   
   Type: TXT
   Name/Host: _dmarc
   Value: v=DMARC1; p=none; rua=mailto:dmarc-reports@leads.momento.family
   
   After 2 weeks if no issues, change to:
   Value: v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@leads.momento.family

OPTION B - Zoho Mail (Budget-friendly)
---------------------------------------
Domain: leads.momento.family

1. PURCHASE DOMAIN ($10-15/year at Namecheap)

2. CREATE ZOHOMAIL ACCOUNT
   - Go to zoho.com/mail
   - Free tier includes 5 users (good for testing)
   
3. CONFIGURE SPF RECORD
   Type: TXT
   Name/Host: @
   Value: v=spf1 include:mail.zoho.com ~all

4. ENABLE DKIM IN ZOHOMAIL
   - Settings -> Email Deliverability -> DKIM
   - Generate key, add as TXT record
   
5. CONFIGURE DMARC
   Type: TXT
   Name/Host: _dmarc
   Value: v=DMARC1; p=none; rua=mailto:dmarc-reports@leads.momento.family

VERIFICATION CHECKLIST - DO BEFORE SENDING ANY CAMPAIGNS
=========================================================

[ ] SPF record added and verified at MXToolbox.com
[ ] DKIM record added and verified  
[ ] DMARC set to p=none (monitoring mode)
[ ] Domain added to Google Postmaster Tools
[ ] Domain added to Microsoft SNDS (Sender Reputation)
[ ] Mailbox created and tested (outreach@domain.com)
[ ] 2FA enabled on admin account
[ ] DNS propagation complete (wait 24-48 hours after changes)

EMAIL WARM-UP SCHEDULE
======================

New domains MUST be warmed up before sending campaigns.

WEEK 1: 20-30 emails/day (mix of personal accounts)
WEEK 2: 40-50 emails/day
WEEK 3: 60-80 emails/day  
WEEK 4: 100+ emails/day (ready for campaigns)

RECOMMENDED WARM-UP TOOLS:
- Warmup Inbox (free tier available) - warmupinbox.com
- Mailwarm.io ($29/month) - mailwarm.io
- Smartlead.ai (free + paid tiers) - smartlead.ai

TESTING EMAIL DELIVERY
======================

BEFORE LAUNCHING CAMPAIGNS:

1. Send test emails to: Gmail, Outlook.com, Yahoo Mail, AOL
2. Check each inbox for spam folder placement
3. Use mail-tester.com for score (90+ desired)
4. Verify with Google Postmaster Tools domain reputation

MONITORING SETUP
================

WEEKLY CHECKS:
- Review DMARC reports (rua= address)
- Check bounce rate (<5% acceptable)
- Monitor spam complaints (<0.1%)
- Verify blacklist status at spamhaus.org

MONTHLY CHECKS:
- Update SPF/DKIM if credentials rotate
- Audit email templates for CAN-SPAM compliance
- Review list hygiene (remove hard bounces)

RESOURCES
=========

- MXToolbox SPF/DKIM/DMARC checker: mxtoolbox.com
- Google Postmaster Tools: postmaster.google.com  
- Microsoft SNDS: sender.reputation.office.com
- Mail-Tester: mail-tester.com
- Spamhaus lookup: spamhaus.org/tools/bl.shtml

NEXT STEPS AFTER DNS SETUP
==========================

1. Wait 24-48 hours for DNS propagation
2. Verify all records at MXToolbox.com
3. Add domain to Google Postmaster Tools
4. Configure warm-up tool
5. Run warm-up for 4 weeks
6. Test with mail-tester.com (score >90)
7. Launch first campaign
