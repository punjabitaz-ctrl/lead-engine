# lead-engine

Lead generation system: validate with a no-code Google Sheet first, build code only after the gate is met.

## Files
- `lead-engine-template.xlsx` — import into Google Sheets (Drive ▸ New ▸ File upload, open with Google Sheets; or Sheets ▸ File ▸ Import). Tabs: START HERE, Config, Leads, Queue, Dashboard, Templates.
- `apps-script/Code.gs` — optional. Adds a "Lead Engine" menu: create Gmail drafts from the Queue (you review and press send), sync sent/replies from Gmail, fill PageSpeed scores. Untested against a live account.

## Pipeline
Collect → Enrich → Validate → Dedupe/Clean → Score/Grade → Outreach drafts → Track. Column colors on the Leads tab show the stage.

## Gate
After ~100 first emails: at least 2 discovery calls and 1 proposal → build the real system. Otherwise change one variable and rerun.
