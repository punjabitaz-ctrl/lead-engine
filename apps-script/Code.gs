/**
 * Lead Engine helpers (OPTIONAL). Paste into Extensions > Apps Script in the Google Sheet.
 * Nothing here sends email: drafts are created in Gmail and YOU review and press send.
 * Untested against a live account: run on the example row / 1-2 leads first.
 */

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Lead Engine')
    .addItem('Create Gmail drafts from Queue', 'createDrafts')
    .addItem('Sync sent / replies from Gmail', 'syncGmail')
    .addItem('Fill mobile PageSpeed scores (12 per run)', 'fillPageSpeed')
    .addItem('Pull clicks and visits from the tracker', 'pullEvents')
    .addToUi();
}

function headerMap_(sheet) {
  const h = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const m = {};
  h.forEach((name, i) => { m[name] = i + 1; });
  return m;
}

// Queue columns: A Rank, B Leads Row, C Company, D Contact, E Email, ... J Subject, K Draft Email
function createDrafts() {
  const ss = SpreadsheetApp.getActive();
  const queue = ss.getSheetByName('Queue');
  const leads = ss.getSheetByName('Leads');
  const col = headerMap_(leads);
  const rows = queue.getRange(5, 1, 25, 11).getValues();
  let n = 0;
  rows.forEach(r => {
    const leadRow = r[1], email = r[4], subject = r[9], body = r[10];
    if (!leadRow || !email || !subject || !body) return;
    GmailApp.createDraft(email, subject, body);
    leads.getRange(leadRow, col['Status']).setValue('Drafted');
    n++;
  });
  SpreadsheetApp.getUi().alert(n + ' draft(s) created. Review them in Gmail > Drafts, edit, and send.');
}

// Marks Drafted rows as Sent (with date) once a sent message exists, and Sent rows as Replied when they answer.
function syncGmail() {
  const leads = SpreadsheetApp.getActive().getSheetByName('Leads');
  const col = headerMap_(leads);
  const last = leads.getLastRow();
  const data = leads.getRange(2, 1, last - 1, leads.getLastColumn()).getValues();
  data.forEach((row, i) => {
    const status = row[col['Status'] - 1], email = row[col['Email'] - 1];
    if (!email || (status !== 'Drafted' && status !== 'Sent')) return;
    const r = i + 2;
    if (status === 'Drafted') {
      const t = GmailApp.search('in:sent to:' + email, 0, 1);
      if (t.length) {
        leads.getRange(r, col['Status']).setValue('Sent');
        leads.getRange(r, col['First Sent Date']).setValue(t[0].getLastMessageDate());
      }
    } else {
      const t = GmailApp.search('from:' + email + ' newer_than:60d', 0, 1);
      if (t.length) {
        leads.getRange(r, col['Status']).setValue('Replied');
        leads.getRange(r, col['Reply Date']).setValue(t[0].getLastMessageDate());
        // Interest level: log the reply on the Events tab (Date, Lead Key, Company, Event)
        const events = SpreadsheetApp.getActive().getSheetByName('Events');
        const next = events.getRange('B:B').getValues().filter(String).length + 1;
        events.getRange(next, 1).setValue(t[0].getLastMessageDate());
        events.getRange(next, 2).setValue(row[col['Dedupe Key'] - 1]);
        events.getRange(next, 4).setValue('Replied');
      }
    }
  });
}

// Needs a free PageSpeed Insights API key: Project Settings > Script properties > PSI_KEY
function fillPageSpeed() {
  const key = PropertiesService.getScriptProperties().getProperty('PSI_KEY');
  if (!key) { SpreadsheetApp.getUi().alert('Add a script property named PSI_KEY first.'); return; }
  const leads = SpreadsheetApp.getActive().getSheetByName('Leads');
  const col = headerMap_(leads);
  const psiCol = col['Mobile PageSpeed (0-100)'];
  const data = leads.getRange(2, 1, leads.getLastRow() - 1, leads.getLastColumn()).getValues();
  let done = 0;
  for (let i = 0; i < data.length && done < 12; i++) {
    let site = String(data[i][col['Website'] - 1] || '').trim();
    if (!site || data[i][psiCol - 1] !== '') continue;
    if (!/^https?:\/\//i.test(site)) site = 'https://' + site;
    try {
      const url = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?strategy=mobile&category=performance&url='
        + encodeURIComponent(site) + '&key=' + key;
      const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
      if (res.getResponseCode() !== 200) continue;
      const score = JSON.parse(res.getContentText()).lighthouseResult.categories.performance.score;
      leads.getRange(i + 2, psiCol).setValue(Math.round(score * 100));
      done++;
    } catch (e) { /* skip this site */ }
  }
}

// Pulls clicks / visits / form fills from the lead-tracker edge function into the Events tab.
// Script properties needed: TRACKER_URL (e.g. https://<project>.supabase.co/functions/v1/lead-tracker), EXPORT_TOKEN.
function pullEvents() {
  const props = PropertiesService.getScriptProperties();
  const base = props.getProperty('TRACKER_URL'), token = props.getProperty('EXPORT_TOKEN');
  if (!base || !token) { SpreadsheetApp.getUi().alert('Add script properties TRACKER_URL and EXPORT_TOKEN first.'); return; }
  const events = SpreadsheetApp.getActive().getSheetByName('Events');
  let since = props.getProperty('LAST_PULL') || '1970-01-01T00:00:00Z', added = 0, more = true;
  while (more) {
    const res = UrlFetchApp.fetch(base + '/export?since=' + encodeURIComponent(since),
      { headers: { 'x-export-token': token }, muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) { SpreadsheetApp.getUi().alert('Tracker returned ' + res.getResponseCode()); return; }
    const body = JSON.parse(res.getContentText());
    const evs = body.events;
    if (evs.length) {
      // Columns C, E, F on the Events tab hold formulas: write only A (date), B (lead key) and D (event).
      const next = events.getRange('B:B').getValues().filter(String).length + 1;
      events.getRange(next, 1, evs.length, 2).setValues(evs.map(e => [new Date(e.ts), e.lead_key]));
      events.getRange(next, 4, evs.length, 1).setValues(evs.map(e => [e.event]));
      added += evs.length;
    }
    since = body.next_since; more = body.more;
  }
  props.setProperty('LAST_PULL', since);
  SpreadsheetApp.getUi().alert(added + ' event(s) added.');
}
