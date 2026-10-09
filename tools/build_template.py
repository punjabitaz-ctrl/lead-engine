import sys, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment

OUT = sys.argv[1]
TEST = len(sys.argv) > 2 and sys.argv[2] == "test"

N = 500                      # lead capacity
R1, RN = 2, N + 1            # first / last data row on Leads
QN = 25                      # queue rows

AR = "Arial"
f_base = Font(name=AR, size=10)
f_bold = Font(name=AR, size=10, bold=True)
f_in = Font(name=AR, size=10, color="0000FF")
f_title = Font(name=AR, size=16, bold=True)
f_sub = Font(name=AR, size=10, italic=True, color="595959")
f_hdr = Font(name=AR, size=10, bold=True)
f_note = Font(name=AR, size=9, italic=True, color="595959")
yellow = PatternFill("solid", fgColor="FFFF99")
grey = PatternFill("solid", fgColor="F2F2F2")
dark = PatternFill("solid", fgColor="1F3864")
f_white = Font(name=AR, size=10, bold=True, color="FFFFFF")
thin = Side(style="thin", color="BFBFBF")
box = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(wrap_text=True, vertical="top")

wb = Workbook()

# ---------------------------------------------------------------- Config
cfg = wb.active
cfg.title = "Config"
S = {}   # key -> absolute address on Config, e.g. Config!$B$4


def put(ws, addr, v, font=f_base, fill=None, fmt=None, al=None, border=None):
    c = ws[addr]
    c.value = v
    c.font = font
    if fill: c.fill = fill
    if fmt: c.number_format = fmt
    if al: c.alignment = al
    if border: c.border = border
    return c


def section(ws, row, text, ncols=3):
    for i in range(1, ncols + 1):
        c = ws.cell(row=row, column=i)
        c.fill = dark
        c.font = f_white
    ws.cell(row=row, column=1).value = text


put(cfg, "A1", "Config — every setting the template uses", f_title)
put(cfg, "A2", "Blue text on yellow = edit me. Everything else in the workbook recalculates from this tab.", f_sub)

section(cfg, 3, "SENDER & OFFER (fills the email drafts)")
rows = [
    ("sender", 4, "Sender name", "[Your name]", "Appears in the email signature"),
    ("biz", 5, "Business name", "[Your business name]", "Appears under your signature"),
    ("addr", 6, "Postal address", "[Street, City, State ZIP]", "REQUIRED by CAN-SPAM in every commercial email"),
    ("portfolio", 7, "Portfolio URL", "https://tazabbas.com/projects", "Provided by you. Shown as proof in email 1"),
    ("booking", 8, "Booking link (optional)", "", "Calendly / Google Calendar link. Leave blank to omit"),
    ("offer", 9, "Offer line", "I build and launch business websites in 72 hours, and can extend that into app and tool development and business marketing strategy.", "One sentence. Edit freely"),
]
for key, r, label, val, note in rows:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", val, f_in, yellow, al=wrap, border=box)
    put(cfg, f"C{r}", note, f_note, al=wrap)
    S[key] = f"Config!$B${r}"

section(cfg, 11, "TARGETING")
for key, r, label, val, note in [
    ("emin", 12, "Employees — minimum", 20, "'Mid-size' lower bound"),
    ("emax", 13, "Employees — maximum", 250, "'Mid-size' upper bound"),
]:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", val, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
    S[key] = f"Config!$B${r}"

section(cfg, 15, "TARGET VERTICALS (pick 1–2 for the first test; leave unused slots blank)")
verts = ["SaaS / Software", "IT Services / MSP", "Fintech", "Consulting & Advisory", "Staffing & Recruiting",
         "Accounting & Legal", "Logistics & Distribution", "Manufacturing", "Healthcare Services", ""]
for i, v in enumerate(verts):
    put(cfg, f"A{16+i}", v, f_in, yellow, border=box)
S["verts"] = "Config!$A$16:$A$25"
put(cfg, "C16", "Starter list — edit or replace. Leads.Vertical should match these exactly.", f_note)

section(cfg, 27, "TARGET METROS (city names only, e.g. Austin; leave unused slots blank)")
metros = ["Austin", "Dallas", "Atlanta"] + [""] * 7
for i, v in enumerate(metros):
    put(cfg, f"A{28+i}", v, f_in, yellow, border=box)
S["metros"] = "Config!$A$28:$A$37"
S["metros2"] = "Config!$E$28:$E$67"
section(cfg, 27, "TARGET METROS (city names only, e.g. Austin; leave unused slots blank)", 5)
put(cfg, "E27", "Overflow metros (column E, rows 28-67)", f_white, dark)
for i in range(40):
    put(cfg, f"E{28+i}", None, f_in, yellow, border=box)
cfg.column_dimensions["E"].width = 30
put(cfg, "C28", "PLACEHOLDERS — replace with your 2–3 test metros.", f_note)

section(cfg, 39, "SCORING POINTS (max 100)")
pts = [
    ("p_vert", 40, "Fit: vertical matches", 10),
    ("p_size", 41, "Fit: employee count in band", 10),
    ("p_metro", 42, "Fit: metro matches", 10),
    ("p_hire", 43, "Urgency: hiring for web/marketing/dev role", 15),
    ("p_psi_poor", 44, "Urgency: mobile PageSpeed is poor", 10),
    ("p_psi_mod", 45, "Urgency: mobile PageSpeed is moderate", 5),
    ("p_old", 46, "Urgency: site looks outdated / not mobile-friendly", 8),
    ("p_exp", 47, "Urgency: expansion / funding / rebrand signal", 7),
    ("p_valid", 48, "Reach: email verified Valid", 10),
    ("p_risky", 49, "Reach: email verified Risky", 5),
    ("p_phone", 50, "Reach: phone number present", 5),
    ("p_li", 51, "Reach: LinkedIn URL present", 5),
    ("p_f1", 52, "Freshness: signal within window 1", 10),
    ("p_f2", 53, "Freshness: signal within window 2", 5),
]
for key, r, label, v in pts:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", v, f_in, yellow, border=box)
    S[key] = f"Config!$B${r}"
put(cfg, "C40", "Fit max 30 · Urgency max 40 · Reach max 20 · Freshness max 10", f_note)

section(cfg, 55, "THRESHOLDS")
ths = [
    ("t_psi_poor", 56, "PageSpeed 'poor' if below", 50, "Mobile score 0–100 (Google's own bands: <50 poor)"),
    ("t_psi_mod", 57, "PageSpeed 'moderate' if below", 75, ""),
    ("t_f1", 58, "Freshness window 1 (days)", 30, ""),
    ("t_f2", 59, "Freshness window 2 (days)", 90, ""),
    ("t_A", 60, "Grade A: total at least", 75, "Only A and B leads reach the Queue"),
    ("t_B", 61, "Grade B: total at least", 60, ""),
    ("t_C", 62, "Grade C: total at least", 40, "Below this = D"),
]
for key, r, label, v, note in ths:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", v, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
    S[key] = f"Config!$B${r}"

section(cfg, 64, "CADENCE & VALIDATION GATE")
cad = [
    ("cap", 65, "Daily send cap (emails/day)", 25, "Keep low while the new domain warms up"),
    ("fu1", 66, "Follow-up 1 after (days)", 3, ""),
    ("fu2", 67, "Follow-up 2 after (days)", 7, ""),
    ("fu3", 68, "Close-out email after (days)", 12, ""),
    ("g_leads", 69, "Gate: leads worked (first emails sent)", 100, "Evaluate only after this many"),
    ("g_calls", 70, "Gate: discovery calls needed", 2, ""),
    ("g_props", 71, "Gate: proposals needed", 1, ""),
]
for key, r, label, v, note in cad:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", v, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
    S[key] = f"Config!$B${r}"

section(cfg, 73, "$100 TEST BUDGET (planned figures are estimates — verify current prices)")
for col, t in zip("ABC", ["Item", "Planned ($)", "Actual ($)"]):
    put(cfg, f"{col}74", t, f_hdr, grey, border=box)
bud = [("Lookalike sending domain", 12), ("Google Workspace mailbox (1st month)", 8),
       ("Email verification credits", 15), ("Data / scraping credits", 25), ("Reserve (tools, other)", 40)]
for i, (lab, v) in enumerate(bud):
    r = 75 + i
    put(cfg, f"A{r}", lab, f_base, border=box)
    put(cfg, f"B{r}", v, f_in, yellow, '$#,##0;($#,##0);-', border=box)
    put(cfg, f"C{r}", None, f_in, yellow, '$#,##0;($#,##0);-', border=box)
put(cfg, "A80", "Total", f_bold, border=box)
put(cfg, "B80", "=SUM(B75:B79)", f_bold, fmt='$#,##0;($#,##0);-', border=box)
put(cfg, "C80", "=SUM(C75:C79)", f_bold, fmt='$#,##0;($#,##0);-', border=box)
put(cfg, "A81", "Budget cap", f_bold)
put(cfg, "B81", 100, f_in, yellow, '$#,##0;($#,##0);-', border=box)
put(cfg, "A82", "Remaining", f_bold)
put(cfg, "B82", "=B81-C80", f_bold, fmt='$#,##0;($#,##0);-')
S["spent"] = "Config!$C$80"
S["remaining"] = "Config!$B$82"
section(cfg, 84, "PRESENCE-GAP POINTS (local-business segments, e.g. medical offices without a web presence)")
for key, r, label, v, note in [
    ("p_nosite", 85, "Urgency: no website (Website Present = N)", 20, "Confirmed by a search or Places lookup, not assumed"),
    ("p_nogbp", 86, "Urgency: no Google business profile (Google Profile Present = N)", 12, ""),
    ("p_thin", 87, "Urgency: profile exists but thin (fewer reviews than the threshold below)", 5, ""),
    ("t_thin", 88, "'Thin' = fewer than this many reviews", 10, ""),
    ("urg_cap", 89, "Urgency cap (total urgency can never exceed)", 40, "Keeps the 100-point model intact"),
]:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", v, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
    S[key] = f"Config!$B${r}"

section(cfg, 91, "INTEREST LEVEL = engagement with YOUR digital properties (scored from the Events tab)")
for key, r, label, v, note in [
    ("eng_window", 92, "Count events from the last N days", 30, ""),
    ("eng_hot", 93, "Hot at or above (points)", 40, ""),
    ("eng_warm", 94, "Warm at or above (points)", 15, "Below this = Cold; no events at all = No contact yet"),
]:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", v, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
    S[key] = f"Config!$B${r}"
for col, t in zip("ABC", ["Event", "Points", "Notes"]):
    put(cfg, f"{col}95", t, f_hdr, grey, border=box)
EVENTS = [
    ("Email sent", 0, "Logged for the record; scores nothing"),
    ("Email opened", 1, "Unreliable: Apple Mail and some clients pre-load images, so opens are inflated"),
    ("Email link clicked", 5, "Needs a tracked link (UTM tag carrying the Dedupe Key)"),
    ("Website visit", 5, "From analytics, matched by the Dedupe Key in the UTM tag"),
    ("Key page visit (portfolio / pricing / contact)", 10, ""),
    ("Form submitted", 25, ""),
    ("Replied", 20, ""),
    ("Positive reply", 30, ""),
    ("Call booked", 40, ""),
    ("Proposal viewed", 30, ""),
    ("Unsubscribed / Not interested", -100, "Also flips Interest Level to Opted out"),
]
for i, (ev, pts_, note) in enumerate(EVENTS):
    r = 96 + i
    put(cfg, f"A{r}", ev, f_base, border=box)
    put(cfg, f"B{r}", pts_, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
S["ev_names"] = f"Config!$A$96:$A${95 + len(EVENTS)}"
S["ev_points"] = f"Config!$B$96:$B${95 + len(EVENTS)}"
section(cfg, 107, "CLICK / VISIT TRACKER (optional; see tracker/README.md)")
put(cfg, "A108", "Tracker base URL", f_bold)
put(cfg, "B108", "https://mzsrtwrbpdpehthwmkwt.supabase.co/functions/v1/lead-tracker", f_in, yellow, al=wrap, border=box)
put(cfg, "C108", "e.g. https://<project>.supabase.co/functions/v1/lead-tracker (no trailing slash). Only used when Link mode = redirect", f_note, al=wrap)
S["tracker"] = "Config!$B$108"
put(cfg, "A109", "Link mode", f_bold)
put(cfg, "B109", "utm", f_in, yellow, border=box)
put(cfg, "C109", "plain = your link as-is · utm = your link + utm tags (use with tracker/track.js; best deliverability) · redirect = log clicks through the tracker URL above", f_note, al=wrap)
S["linkmode"] = "Config!$B$109"
_dvm = DataValidation(type="list", formula1='"plain,utm,redirect"', allow_blank=False)
_dvm.add("B109")
cfg.add_data_validation(_dvm)
section(cfg, 111, "PRACTICE SIZE (filter large groups on the Leads tab: filter the Size Class column)")
for key, r, label, v, note in [
    ("size_small", 112, "Small practice: up to this many clinicians", 5, "1 clinician = Solo; 2 up to this number = Small"),
    ("size_med", 113, "Medium practice: up to this many clinicians", 15, "Above this = Large"),
    ("excl_large", 114, "Exclude Large practices from Queue and Call Queue (Y/N)", "N", "Rows stay on Leads so you can still filter and review them"),
]:
    put(cfg, f"A{r}", label, f_bold)
    put(cfg, f"B{r}", v, f_in, yellow, border=box)
    put(cfg, f"C{r}", note, f_note)
    S[key] = f"Config!$B${r}"
_dvx = DataValidation(type="list", formula1='"Y,N"', allow_blank=False)
_dvx.add("B114")
cfg.add_data_validation(_dvx)
for col, w in zip("ABC", [62, 62, 62]):
    cfg.column_dimensions[col].width = w

# ---------------------------------------------------------------- Templates
tp = wb.create_sheet("Templates")
put(tp, "A1", "Templates — email copy, follow-ups and other channels", f_title)
put(tp, "A2", "Row 5–10 drive the Draft Subject / Draft Email 1 columns on Leads. Edit the wording; keep the {tokens}. "
              "Tokens: {first_name} {company} {website} {city} {signal_detail} {site_issue} {reviews} {signal_line} {offer_line} "
              "{portfolio_url} {booking_link} {sender_name} {business_name} {postal_address}", f_sub, al=wrap)
tp.merge_cells("A2:D2")
tp.row_dimensions[2].height = 42
for col, t in zip("ABCD", ["Signal Type", "Signal Line (becomes {signal_line})", "Subject", "Body"]):
    put(tp, f"{col}4", t, f_hdr, grey, border=box)

BODY = ("Hi {first_name},\n\n{signal_line}\n\n{offer_line}\n\n"
        "If a fast, fixed-scope project would help {company}, I'm happy to send a quick plan — no obligation. "
        "A few recent launches (AYiN Advisors, Historical Philly, Al Saboot Builders, Qbit Edge Technologies) are at {portfolio_url}\n\nWorth a 15-minute call this week?{booking_link}\n\n"
        "{sender_name}\n{business_name} · {postal_address}\n"
        "If you'd rather not hear from me, just reply \"no thanks\" and I won't contact you again.")
tmpl = [
    ("Hiring", "I saw that {company} is hiring for {signal_detail}, which is often a sign a digital project is on the way.",
     "{company}'s digital project — quick idea"),
    ("Weak Site", "I took a look at {website} and {site_issue}.", "Quick note on {website}"),
    ("Expansion", "Congratulations on {signal_detail}. Growth like that usually puts pressure on the website.",
     "Congrats, {company} — quick idea"),
    ("General", "I came across {company} while researching companies in {city}.", "Idea for {company}'s website"),
    ("No Presence", "I searched for {company} in {city} and couldn't find a website or a claimed Google listing, so people looking for a practice like yours online may not be finding you.",
     "Is {company} easy to find online?"),
    ("Thin Profile", "I noticed {company} has only {reviews} Google reviews, and patients often check reviews before they book.",
     "A quick note on {company}'s Google reviews"),
]
for i, (sig, line, subj) in enumerate(tmpl):
    r = 5 + i
    put(tp, f"A{r}", sig, f_bold, al=wrap, border=box)
    put(tp, f"B{r}", line, f_in, yellow, al=wrap, border=box)
    put(tp, f"C{r}", subj, f_in, yellow, al=wrap, border=box)
    put(tp, f"D{r}", BODY, f_in, yellow, al=wrap, border=box)
    tp.row_dimensions[r].height = 190

put(tp, "A11", "Follow-ups & other channels (copy / paste — these are not formula-driven)", f_bold)
for col, t in zip("ABC", ["Use", "Channel", "Text"]):
    put(tp, f"{col}12", t, f_hdr, grey, border=box)
other = [
    ("Follow-up 1 (day 3)", "Email",
     "Hi {first_name},\n\nQuick bump on my note about {company}. If timing is the issue, I can have a first draft in front of you "
     "within 72 hours of kickoff. Happy to share a one-page plan first.\n\n{sender_name}"),
    ("Follow-up 2 (day 7)", "Email",
     "Hi {first_name},\n\nOne more idea: if you send me the 2–3 pages that matter most, I'll mock up how they could look and "
     "send it over — no charge, no strings.\n\n{sender_name}"),
    ("Close-out (day 12)", "Email",
     "Hi {first_name},\n\nI don't want to clutter your inbox, so this is my last note. If a website or digital project comes up "
     "for {company}, you can reach me at any time.\n\n{sender_name}"),
    ("Connection note (<300 chars)", "LinkedIn — manual only",
     "Hi {first_name}, I work with mid-size companies on fast website and digital launches. Saw {company} {signal_detail}. "
     "Would be good to connect."),
    ("30-second opener", "Phone",
     "Hi {first_name}, this is {sender_name}. I sent you a short note about {company}'s website. I'll be brief: I build and "
     "launch business websites in 72 hours. Is a website or digital project on your plate this quarter?"),
    ("Voicemail", "Phone",
     "Hi {first_name}, {sender_name} here. I emailed about {company}'s website and thought a quick call might be easier. "
     "I'm at [phone]. Thanks."),
    ("After they reply or share WhatsApp", "WhatsApp — warm leads ONLY",
     "Hi {first_name}, {sender_name} here, following up on our email thread. Happy to continue here if easier. "
     "Do you have 15 minutes this week?"),
    ("Call opener — no web presence", "Phone",
     "Hi, may I speak with {first_name} or whoever handles the practice's marketing? This is {sender_name}. I'm a local "
     "web and marketing specialist. I searched for {company} online and couldn't find a website or Google listing. "
     "Quick question: how do most of your new patients find you today?"),
    ("Voicemail — no web presence", "Phone",
     "Hi, this is {sender_name}. I searched for {company} online and couldn't find a website or Google listing, and I help "
     "practices fix that quickly. I'll send a short note, or you can reach me at [phone]. Thank you."),
    ("Postcard / letter copy", "Physical mail",
     "FRONT: Can new patients find {company} online?\nBACK: I searched for {company} in {city} and couldn't find a website or "
     "claimed Google listing. I build practice websites in 72 hours and set up your local search presence. Call "
     "{sender_name} at [phone]. {business_name}, {postal_address}. No obligation. (Check NJ advertising rules, "
     "N.J.A.C. 13:35-6.10, before making any patient-facing claim.)"),
]
for i, (use, ch, txt) in enumerate(other):
    r = 13 + i
    put(tp, f"A{r}", use, f_bold, al=wrap, border=box)
    put(tp, f"B{r}", ch, f_base, al=wrap, border=box)
    put(tp, f"C{r}", txt, f_in, yellow, al=wrap, border=box)
    tp.merge_cells(f"C{r}:D{r}")
    tp.row_dimensions[r].height = 78
for col, w in zip("ABCD", [30, 46, 46, 78]):
    tp.column_dimensions[col].width = w

# ---------------------------------------------------------------- Leads
ld = wb.create_sheet("Leads")
STAGES = {
    "collect": ("DDEBF7", True), "enrich": ("E2EFDA", True), "validate": ("FFF2CC", True),
    "clean": ("EDEDED", False), "score": ("FCE4D6", False), "outreach": ("E4DFEC", False), "track": ("D9E1F2", True),
}
COLS = [
    ("source", "Source", "collect", 14), ("company", "Company", "collect", 28), ("website", "Website", "collect", 28),
    ("phone", "Phone", "collect", 15), ("city", "City", "collect", 12), ("state", "State", "collect", 7),
    ("vertical", "Vertical", "collect", 22), ("specialty", "Specialty", "collect", 22), ("npi", "NPI", "collect", 12),
    ("emp", "Employees (est.)", "collect", 11),
    ("hiring", "Hiring Signal (Y/N)", "collect", 10), ("expand", "Expansion Signal (Y/N)", "collect", 11),
    ("detail", "Signal Detail", "collect", 32), ("sigdate", "Signal Date", "collect", 12),
    ("first", "First Name", "enrich", 12), ("last", "Last Name", "enrich", 12), ("title", "Title", "enrich", 20),
    ("email", "Email", "enrich", 28), ("linkedin", "LinkedIn URL", "enrich", 24),
    ("psi", "Mobile PageSpeed (0-100)", "enrich", 11), ("outdated", "Outdated Site (Y/N)", "enrich", 10),
    ("hasweb", "Website Present (Y/N)", "enrich", 10), ("hasgbp", "Google Profile Present (Y/N)", "enrich", 11),
    ("reviews", "Review Count", "enrich", 9), ("providers", "Providers (est.)", "enrich", 10), ("sizeov", "Size Override", "enrich", 10),
    ("estatus", "Email Status", "validate", 12),
    ("key", "Dedupe Key", "clean", 24), ("dup", "Duplicate?", "clean", 10), ("sizeclass", "Size Class", "clean", 10),
    ("fit", "Fit (0-30)", "score", 8), ("urg", "Urgency (0-40)", "score", 9), ("reach", "Reach (0-20)", "score", 8),
    ("fresh", "Fresh (0-10)", "score", 8), ("total", "Total (0-100)", "score", 9), ("grade", "Grade", "score", 7),
    ("why", "Why This Lead", "score", 50),
    ("sig", "Primary Signal", "outreach", 12), ("sigline", "Signal Line", "outreach", 40),
    ("tlink", "Tracked Link", "outreach", 30), ("subj", "Draft Subject", "outreach", 30), ("body", "Draft Email 1", "outreach", 40),
    ("elig", "Eligible (1/0)", "outreach", 9), ("rank", "Queue Rank", "outreach", 8),
    ("channel", "Best Channel", "outreach", 11), ("callelig", "Call Eligible (1/0)", "outreach", 9),
    ("callrank", "Call Rank", "outreach", 8),
    ("status", "Status", "track", 14), ("sent", "First Sent Date", "track", 12), ("fus", "Follow-ups Sent", "track", 10),
    ("fudue", "Follow-Up Due", "track", 16), ("reply", "Reply Date", "track", 12), ("call", "Call Date", "track", 12),
    ("prop", "Proposal Date", "track", 12), ("won", "Won Date", "track", 12), ("value", "Deal Value ($)", "track", 12),
    ("notes", "Notes", "track", 36), ("eng", "Engagement Pts", "track", 10), ("interest", "Interest Level", "track", 14),
]
CI = {k: i + 1 for i, (k, *_) in enumerate(COLS)}
CL = {k: get_column_letter(i) for k, i in CI.items()}


def c(k, r): return f"{CL[k]}{r}"
def rng(k, abs_=True): return f"Leads!${CL[k]}${R1}:${CL[k]}${RN}"


for k, name, stage, w in COLS:
    cell = ld.cell(row=1, column=CI[k], value=name)
    cell.font = f_hdr
    cell.fill = PatternFill("solid", fgColor=STAGES[stage][0])
    cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    cell.border = box
    ld.column_dimensions[CL[k]].width = w
ld.row_dimensions[1].height = 44
ld.freeze_panes = "C2"

KEY_X = lambda r: (f'LOWER(TRIM(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE({c("website", r)},"https://",""),"http://",""),"www.","")))')


def formulas(r):
    B = c("company", r)
    f = {}
    x = KEY_X(r)
    f["key"] = (f'=IF({B}="","",IF({c("website", r)}="",LOWER(TRIM({B}))&"|"&LOWER(TRIM({c("city", r)})),'
                f'IFERROR(LEFT({x},FIND("/",{x})-1),{x})))')
    f["dup"] = f'=IF({c("key", r)}="","",IF(COUNTIF(${CL["key"]}${R1}:{c("key", r)},{c("key", r)})>1,"DUP",""))'
    f["fit"] = (f'=IF({B}="","",IF(AND({c("vertical", r)}<>"",COUNTIF({S["verts"]},{c("vertical", r)})>0),{S["p_vert"]},0)'
                f'+IF(AND(ISNUMBER({c("emp", r)}),{c("emp", r)}>={S["emin"]},{c("emp", r)}<={S["emax"]}),{S["p_size"]},0)'
                f'+IF(AND({c("city", r)}<>"",COUNTIF({S["metros"]},{c("city", r)})+COUNTIF({S["metros2"]},{c("city", r)})>0),{S["p_metro"]},0))')
    f["urg"] = (f'=IF({B}="","",MIN({S["urg_cap"]},IF({c("hiring", r)}="Y",{S["p_hire"]},0)'
                f'+IF(ISNUMBER({c("psi", r)}),IF({c("psi", r)}<{S["t_psi_poor"]},{S["p_psi_poor"]},'
                f'IF({c("psi", r)}<{S["t_psi_mod"]},{S["p_psi_mod"]},0)),0)'
                f'+IF({c("outdated", r)}="Y",{S["p_old"]},0)+IF({c("expand", r)}="Y",{S["p_exp"]},0)'
                f'+IF({c("hasweb", r)}="N",{S["p_nosite"]},0)'
                f'+IF({c("hasgbp", r)}="N",{S["p_nogbp"]},IF(AND(ISNUMBER({c("reviews", r)}),{c("reviews", r)}<{S["t_thin"]}),{S["p_thin"]},0))))')
    f["reach"] = (f'=IF({B}="","",IF({c("estatus", r)}="Valid",{S["p_valid"]},IF({c("estatus", r)}="Risky",{S["p_risky"]},0))'
                  f'+IF({c("phone", r)}<>"",{S["p_phone"]},0)+IF({c("linkedin", r)}<>"",{S["p_li"]},0))')
    f["fresh"] = (f'=IF({B}="","",IF(ISNUMBER({c("sigdate", r)}),IF(TODAY()-{c("sigdate", r)}<={S["t_f1"]},{S["p_f1"]},'
                  f'IF(TODAY()-{c("sigdate", r)}<={S["t_f2"]},{S["p_f2"]},0)),0))')
    f["total"] = f'=IF({B}="","",{c("fit", r)}+{c("urg", r)}+{c("reach", r)}+{c("fresh", r)})'
    f["grade"] = (f'=IF({B}="","",IF({c("total", r)}>={S["t_A"]},"A",IF({c("total", r)}>={S["t_B"]},"B",'
                  f'IF({c("total", r)}>={S["t_C"]},"C","D"))))')
    f["why"] = (f'=IF({B}="","",TRIM(IF({c("detail", r)}<>"",{c("detail", r)}&". ","")'
                f'&IF(ISNUMBER({c("psi", r)}),"Mobile PageSpeed "&{c("psi", r)}&"/100. ","")'
                f'&IF({c("outdated", r)}="Y","Site looks outdated. ","")'
                f'&IF({c("hasweb", r)}="N","No website. ","")&IF({c("hasgbp", r)}="N","No Google profile. ","")'
                f'&IF({c("estatus", r)}="Valid","Email verified.",IF({c("estatus", r)}="Risky","Email risky.","No verified email."))))')
    f["sig"] = (f'=IF({B}="","",IF({c("hiring", r)}="Y","Hiring",IF(OR({c("hasweb", r)}="N",{c("hasgbp", r)}="N"),"No Presence",'
                f'IF(OR(AND(ISNUMBER({c("psi", r)}),{c("psi", r)}<{S["t_psi_poor"]}),'
                f'{c("outdated", r)}="Y"),"Weak Site",IF(AND(ISNUMBER({c("reviews", r)}),{c("reviews", r)}<{S["t_thin"]}),"Thin Profile",'
                f'IF({c("expand", r)}="Y","Expansion","General"))))))')
    detail = f'IF({c("detail", r)}="","a digital role",{c("detail", r)})'
    site_issue = (f'IF(ISNUMBER({c("psi", r)}),"Google\'s PageSpeed test scores it "&{c("psi", r)}&"/100 on mobile",'
                  f'IF({c("detail", r)}<>"",{c("detail", r)},"it looks dated on mobile"))')
    line = f'INDEX(Templates!$B$5:$B$10,MATCH({c("sig", r)},Templates!$A$5:$A$10,0))'
    f["sigline"] = (f'=IF({B}="","",SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE({line},"{{company}}",{B}),'
                    f'"{{website}}",{c("website", r)}),"{{city}}",{c("city", r)}),"{{signal_detail}}",{detail}),'
                    f'"{{site_issue}}",{site_issue}),"{{reviews}}",{c("reviews", r)}))')
    f["subj"] = (f'=IF({B}="","",SUBSTITUTE(SUBSTITUTE(INDEX(Templates!$C$5:$C$10,MATCH({c("sig", r)},Templates!$A$5:$A$10,0)),'
                 f'"{{company}}",{B}),"{{website}}",{c("website", r)}))')
    body = f'INDEX(Templates!$D$5:$D$10,MATCH({c("sig", r)},Templates!$A$5:$A$10,0))'
    booking = f'IF({S["booking"]}="","",CHAR(10)&"Book directly: "&{S["booking"]})'
    f["body"] = (f'=IF({B}="","",SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE('
                 f'{body},"{{first_name}}",IF({c("first", r)}="","there",{c("first", r)})),"{{signal_line}}",{c("sigline", r)}),'
                 f'"{{offer_line}}",{S["offer"]}),"{{portfolio_url}}",{c("tlink", r)}),"{{booking_link}}",{booking}),'
                 f'"{{sender_name}}",{S["sender"]}),"{{business_name}}",{S["biz"]}),"{{postal_address}}",{S["addr"]}),'
                 f'"{{company}}",{B}))')
    f["elig"] = (f'=IF({B}="",0,IF(AND(OR({c("grade", r)}="A",{c("grade", r)}="B"),{c("estatus", r)}="Valid",'
                 f'{c("dup", r)}="",{c("email", r)}<>"",OR({c("status", r)}="New",{c("status", r)}=""),'
                 f'LEFT({c("source", r)},7)<>"EXAMPLE",OR({S["excl_large"]}<>"Y",{c("sizeclass", r)}<>"Large")),1,0))')
    prev = r - 1
    f["rank"] = (f'=IF({c("elig", r)}=1,COUNTIFS(${CL["elig"]}${R1}:${CL["elig"]}${RN},1,${CL["total"]}${R1}:${CL["total"]}${RN},">"&{c("total", r)})'
                 f'+COUNTIFS(${CL["elig"]}$1:{CL["elig"]}{prev},1,${CL["total"]}$1:{CL["total"]}{prev},{c("total", r)})+1,"")')
    f["fudue"] = (f'=IF(OR({B}="",{c("status", r)}<>"Sent",NOT(ISNUMBER({c("sent", r)}))),"",'
                  f'IF(AND(N({c("fus", r)})=0,TODAY()-{c("sent", r)}>={S["fu1"]}),"Follow-up 1",'
                  f'IF(AND(N({c("fus", r)})=1,TODAY()-{c("sent", r)}>={S["fu2"]}),"Follow-up 2",'
                  f'IF(AND(N({c("fus", r)})=2,TODAY()-{c("sent", r)}>={S["fu3"]}),"Close-out",""))))')
    f["tlink"] = (f'=IF({B}="","",IF({S["linkmode"]}="utm",{S["portfolio"]}&IF(ISNUMBER(FIND("?",{S["portfolio"]})),"&","?")'
                  f'&"utm_source=leadengine&utm_content="&_xlfn.ENCODEURL({c("key", r)}),'
                  f'IF(AND({S["linkmode"]}="redirect",{S["tracker"]}<>""),{S["tracker"]}&"/t?l="&_xlfn.ENCODEURL({c("key", r)})'
                  f'&"&to="&_xlfn.ENCODEURL({S["portfolio"]}),{S["portfolio"]})))')
    f["sizeclass"] = (f'=IF({B}="","",IF({c("sizeov", r)}<>"",{c("sizeov", r)},IF(ISNUMBER({c("providers", r)}),'
                      f'IF({c("providers", r)}<=1,"Solo",IF({c("providers", r)}<={S["size_small"]},"Small",IF({c("providers", r)}<={S["size_med"]},"Medium","Large"))),"Unknown")))')
    f["channel"] = (f'=IF({B}="","",IF(AND({c("estatus", r)}="Valid",{c("email", r)}<>""),"Email",'
                    f'IF({c("phone", r)}<>"","Phone","Find contact")))')
    f["callelig"] = (f'=IF({B}="",0,IF(AND(OR({c("grade", r)}="A",{c("grade", r)}="B",{c("grade", r)}="C"),{c("phone", r)}<>"",'
                     f'{c("dup", r)}="",OR({c("status", r)}="New",{c("status", r)}=""),LEFT({c("source", r)},7)<>"EXAMPLE",'
                     f'OR({S["excl_large"]}<>"Y",{c("sizeclass", r)}<>"Large")),1,0))')
    f["callrank"] = (f'=IF({c("callelig", r)}=1,COUNTIFS(${CL["callelig"]}${R1}:${CL["callelig"]}${RN},1,${CL["total"]}${R1}:${CL["total"]}${RN},">"&{c("total", r)})'
                     f'+COUNTIFS(${CL["callelig"]}$1:{CL["callelig"]}{prev},1,${CL["total"]}$1:{CL["total"]}{prev},{c("total", r)})+1,"")')
    ev_key, ev_date, ev_pts, ev_name = "Events!$B$2:$B$2001", "Events!$A$2:$A$2001", "Events!$E$2:$E$2001", "Events!$D$2:$D$2001"
    f["eng"] = (f'=IF({B}="","",SUMIFS({ev_pts},{ev_key},{c("key", r)},{ev_date},">="&(TODAY()-{S["eng_window"]})))')
    f["interest"] = (f'=IF({B}="","",IF(OR({c("status", r)}="Do Not Contact",COUNTIFS({ev_key},{c("key", r)},{ev_name},"Unsubscribed / Not interested")>0),"Opted out",'
                     f'IF({c("eng", r)}>={S["eng_hot"]},"Hot",IF({c("eng", r)}>={S["eng_warm"]},"Warm",'
                     f'IF(COUNTIFS({ev_key},{c("key", r)})=0,"No contact yet","Cold")))))')
    return f


FORMULA_KEYS = {"key", "dup", "fit", "urg", "reach", "fresh", "total", "grade", "why", "sig", "sigline", "subj", "body",
                "elig", "rank", "fudue", "tlink", "sizeclass", "channel", "callelig", "callrank", "eng", "interest"}
DATE_KEYS = {"sigdate", "sent", "reply", "call", "prop", "won"}
today = datetime.date.today()

example = {
    "source": "EXAMPLE - clear this row", "company": "Example Logistics Co.", "website": "https://www.example.com/about",
    "phone": "(512) 555-0100", "city": "Austin", "state": "TX", "vertical": "Logistics & Distribution", "emp": 85,
    "hiring": "Y", "expand": "N", "detail": "Web Developer (job posting)", "sigdate": today - datetime.timedelta(days=10),
    "first": "Jordan", "last": "Lee", "title": "VP Operations", "email": "jordan@example.com",
    "linkedin": "https://www.linkedin.com/in/example", "psi": 38, "outdated": "Y", "estatus": "Unverified", "status": "New",
}
tests = [
    # company, website, city, vertical, emp, hiring, expand, psi, outdated, estatus, daysago, phone, li, status, extra
    dict(source="Indeed", company="Alpha Freight", website="http://www.alphafreight.test/", city="Austin", vertical="Logistics & Distribution",
         emp=120, hiring="Y", expand="N", psi=30, outdated="Y", estatus="Valid", sigdate=today - datetime.timedelta(days=5),
         phone="555", linkedin="x", first="Ann", email="ann@alphafreight.test", status="New", detail="Web Developer"),
    dict(source="Maps", company="Alpha Freight LLC", website="https://alphafreight.test/contact", city="Austin", vertical="Logistics & Distribution",
         emp=120, hiring="Y", expand="N", psi=30, outdated="Y", estatus="Valid", sigdate=today - datetime.timedelta(days=5),
         phone="555", linkedin="x", first="Ann", email="ann2@alphafreight.test", status="New", detail="Web Developer"),
    dict(source="Maps", company="Beta Systems", website="https://beta.test", city="Dallas", vertical="IT Services / MSP",
         emp=60, hiring="N", expand="Y", psi=60, outdated="N", estatus="Valid", sigdate=today - datetime.timedelta(days=40),
         phone="555", linkedin="", first="Bo", email="bo@beta.test", status="New", detail="Series A announced"),
    dict(source="Maps", company="Gamma Co", website="", city="Boise", vertical="Retail", emp=5, hiring="N", expand="N",
         estatus="Invalid", status="New"),
    dict(source="Indeed", company="Delta Fintech", website="https://delta.test", city="Atlanta", vertical="Fintech", emp=200,
         hiring="Y", expand="Y", psi=45, outdated="Y", estatus="Valid", sigdate=today - datetime.timedelta(days=2),
         phone="555", linkedin="x", first="", email="info@delta.test", status="New", detail="Marketing Manager"),
    dict(source="Indeed", company="Epsilon Group", website="https://epsilon.test", city="Austin", vertical="Fintech", emp=90,
         hiring="Y", expand="N", psi=80, outdated="N", estatus="Valid", sigdate=today - datetime.timedelta(days=60),
         phone="555", linkedin="x", first="Eve", email="eve@epsilon.test", status="Sent", sent=today - datetime.timedelta(days=4),
         fus=0, reply=None, detail="Developer"),
    dict(source="NPPES", company="Garden State Family Care", website="", city="Austin", vertical="Healthcare Services", emp=8,
         hasweb="N", hasgbp="N", phone="555-0101", estatus="Unverified", status="New", sigdate=today - datetime.timedelta(days=5),
         specialty="Family Medicine", npi="1234567890"),
]
rows_in = [example] if not TEST else tests
for r in range(R1, RN + 1):
    fm = formulas(r)
    data = rows_in[r - R1] if r - R1 < len(rows_in) else {}
    for k, name, stage, w in COLS:
        cell = ld.cell(row=r, column=CI[k])
        if k in FORMULA_KEYS:
            cell.value = fm[k]
            cell.font = f_base
        else:
            v = data.get(k)
            cell.value = v
            cell.font = f_in
        if k in DATE_KEYS: cell.number_format = "yyyy-mm-dd"
        if k == "value": cell.number_format = '$#,##0;($#,##0);-'
        if k == "grade": cell.alignment = Alignment(horizontal="center")

# validations
def dv_list(f1, keys, warn=False):
    dv = DataValidation(type="list", formula1=f1, allow_blank=True)
    if warn:
        dv.errorStyle = "warning"
        dv.error = "Not in the Config list — OK if intentional."
    for k in keys:
        dv.add(f"{CL[k]}{R1}:{CL[k]}{RN}")
    ld.add_data_validation(dv)


dv_list('"Y,N"', ["hiring", "expand", "outdated", "hasweb", "hasgbp"])
dv_list('"Solo,Small,Medium,Large"', ["sizeov"])
dv_list('"Unverified,Valid,Risky,Invalid"', ["estatus"])
dv_list('"New,Drafted,Sent,Replied,Call Booked,Proposal,Won,Lost,Do Not Contact"', ["status"])
dv_list('"Indeed,Google Maps,Directory,Referral,LinkedIn (manual),Other"', ["source"], warn=True)
dv_list(f'={S["verts"]}', ["vertical"], warn=True)

# conditional formats
g = CL["grade"]
for val, color in [("A", "C6E0B4"), ("B", "E2EFDA"), ("C", "FFE699"), ("D", "D9D9D9")]:
    ld.conditional_formatting.add(f"{g}{R1}:{g}{RN}", FormulaRule(formula=[f'${g}{R1}="{val}"'], fill=PatternFill("solid", bgColor=color)))
d = CL["dup"]
ld.conditional_formatting.add(f"{d}{R1}:{d}{RN}", FormulaRule(formula=[f'${d}{R1}="DUP"'], fill=PatternFill("solid", bgColor="F4B084")))
fu = CL["fudue"]
ld.conditional_formatting.add(f"{fu}{R1}:{fu}{RN}", FormulaRule(formula=[f'LEN(${fu}{R1})>0'], fill=PatternFill("solid", bgColor="FFD966")))
es = CL["estatus"]
ld.conditional_formatting.add(f"{es}{R1}:{es}{RN}", FormulaRule(formula=[f'${es}{R1}="Invalid"'], fill=PatternFill("solid", bgColor="F8CBAD")))
ld.auto_filter.ref = f"A1:{CL['interest']}{RN}"

# ---------------------------------------------------------------- Queue
qu = wb.create_sheet("Queue")
put(qu, "A1", "Today's Queue — top-ranked eligible leads with drafts ready for your review", f_title)
put(qu, "A2", "Eligible = Grade A/B, Email Status Valid, not a duplicate, Status New. Review the draft, edit the Leads row if needed, "
              "then run Lead Engine ▸ Create Gmail drafts (Apps Script) or copy/paste. Nothing is sent automatically.", f_sub, al=wrap)
qu.merge_cells("A2:K2")
qu.row_dimensions[2].height = 30
qhead = ["Rank", "Leads Row", "Company", "Contact", "Email", "Grade", "Score", "Primary Signal", "Why This Lead", "Subject", "Draft Email"]
for i, t in enumerate(qhead):
    cell = qu.cell(row=4, column=i + 1, value=t)
    cell.font = f_hdr; cell.fill = PatternFill("solid", fgColor="E4DFEC"); cell.border = box
    cell.alignment = Alignment(wrap_text=True, vertical="center")
LR = f"$1:${RN}"
def idx(k): return f"INDEX(Leads!${CL[k]}$1:${CL[k]}${RN},$B{{r}})"
for i in range(QN):
    r = 5 + i
    qu[f"A{r}"] = i + 1
    qu[f"B{r}"] = f'=IF(A{r}>{S["cap"]},"",IFERROR(MATCH(A{r},Leads!${CL["rank"]}$1:${CL["rank"]}${RN},0),""))'
    qu[f"C{r}"] = f'=IF($B{r}="","",{idx("company").format(r=r)})'
    qu[f"D{r}"] = f'=IF($B{r}="","",TRIM({idx("first").format(r=r)}&" "&{idx("last").format(r=r)}))'
    qu[f"E{r}"] = f'=IF($B{r}="","",{idx("email").format(r=r)})'
    qu[f"F{r}"] = f'=IF($B{r}="","",{idx("grade").format(r=r)})'
    qu[f"G{r}"] = f'=IF($B{r}="","",{idx("total").format(r=r)})'
    qu[f"H{r}"] = f'=IF($B{r}="","",{idx("sig").format(r=r)})'
    qu[f"I{r}"] = f'=IF($B{r}="","",{idx("why").format(r=r)})'
    qu[f"J{r}"] = f'=IF($B{r}="","",{idx("subj").format(r=r)})'
    qu[f"K{r}"] = f'=IF($B{r}="","",{idx("body").format(r=r)})'
    for col in "ABCDEFGHIJK":
        qu[f"{col}{r}"].font = f_base
        qu[f"{col}{r}"].alignment = wrap
        qu[f"{col}{r}"].border = box
    qu.row_dimensions[r].height = 120
for col, w in zip("ABCDEFGHIJK", [6, 8, 24, 18, 26, 7, 7, 12, 36, 30, 70]):
    qu.column_dimensions[col].width = w
qu.freeze_panes = "C5"

# ---------------------------------------------------------------- Events (interest level)
ev = wb.create_sheet("Events")
put(ev, "A1", "Date", f_hdr, grey, border=box)
for col, t in zip("ABCDEFG", ["Date", "Lead Key (Dedupe Key from Leads)", "Company (auto)", "Event", "Points (auto)",
                               "In window? (auto)", "Notes"]):
    put(ev, f"{col}1", t, f_hdr, grey, border=box, al=Alignment(wrap_text=True, vertical="center"))
ev.row_dimensions[1].height = 32
EV_N = 2000
for r in range(2, EV_N + 2):
    ev[f"C{r}"] = f'=IF(B{r}="","",IFERROR(INDEX({rng("company")},MATCH(B{r},{rng("key")},0)),"(key not found on Leads)"))'
    ev[f"E{r}"] = f'=IF(D{r}="","",IFERROR(INDEX({S["ev_points"]},MATCH(D{r},{S["ev_names"]},0)),0))'
    ev[f"F{r}"] = f'=IF(A{r}="","",IF(A{r}>=TODAY()-{S["eng_window"]},1,0))'
    for col in "ABCDEFG":
        ev[f"{col}{r}"].font = f_in if col in "ABDG" else f_base
    ev[f"A{r}"].number_format = "yyyy-mm-dd"
if TEST:
    for i, (k, e) in enumerate([("alphafreight.test", "Email link clicked"), ("alphafreight.test", "Key page visit (portfolio / pricing / contact)"),
                                ("alphafreight.test", "Replied"), ("beta.test", "Call booked"), ("epsilon.test", "Replied"),
                                ("epsilon.test", "Unsubscribed / Not interested"), ("delta.test", "Email sent")]):
        ev[f"A{3+i}"], ev[f"B{3+i}"], ev[f"D{3+i}"] = today - datetime.timedelta(days=3), k, e
ev["A2"], ev["B2"], ev["D2"], ev["G2"] = (today - datetime.timedelta(days=2), "example.com", "Email link clicked",
                                          "EXAMPLE row: clear A2, B2, D2, G2 before use")
dv_ev = DataValidation(type="list", formula1=f'={S["ev_names"]}', allow_blank=True)
dv_ev.add(f"D2:D{EV_N + 1}")
ev.add_data_validation(dv_ev)
for col, w in zip("ABCDEFG", [12, 34, 30, 40, 10, 10, 46]):
    ev.column_dimensions[col].width = w
ev.freeze_panes = "A2"
put(ev, "I1", "How to log an event", f_bold)
for i, t in enumerate([
    "1. Copy the lead's Dedupe Key from the Leads tab into column B.",
    "2. Pick the event in column D. Points come from the Config tab.",
    "3. Leads ▸ Engagement Pts sums events inside the window; Interest Level = Hot / Warm / Cold / Opted out.",
    "Tracked links: add ?utm_source=leadengine&utm_content=<Dedupe Key> to every link you send, then log clicks and",
    "visits from your analytics. Replies come from Lead Engine ▸ Sync (Apps Script) or by hand.",
]):
    put(ev, f"I{2+i}", t, f_note)
ev.column_dimensions["I"].width = 90

# ---------------------------------------------------------------- Call Queue
cq = wb.create_sheet("Call Queue")
put(cq, "A1", "Call Queue — phone-first leads (no verified email needed)", f_title)
put(cq, "A2", "Call Eligible = Grade A/B/C, phone present, not a duplicate, Status New. Dial by hand, business lines only; "
              "set Status and dates on Leads afterwards.", f_sub, al=wrap)
cq.merge_cells("A2:I2")
for i, t in enumerate(["Rank", "Leads Row", "Company", "Contact", "Phone", "Grade", "Score", "Why This Lead", "Call Opener"]):
    cell = cq.cell(row=4, column=i + 1, value=t)
    cell.font = f_hdr; cell.fill = PatternFill("solid", fgColor="E4DFEC"); cell.border = box
for i in range(QN):
    r = 5 + i
    cq[f"A{r}"] = i + 1
    cq[f"B{r}"] = f'=IF(A{r}>{S["cap"]},"",IFERROR(MATCH(A{r},Leads!${CL["callrank"]}$1:${CL["callrank"]}${RN},0),""))'
    def ix(k): return f'INDEX(Leads!${CL[k]}$1:${CL[k]}${RN},$B{r})'
    cq[f"C{r}"] = f'=IF($B{r}="","",{ix("company")})'
    cq[f"D{r}"] = f'=IF($B{r}="","",TRIM({ix("first")}&" "&{ix("last")}))'
    cq[f"E{r}"] = f'=IF($B{r}="","",{ix("phone")})'
    cq[f"F{r}"] = f'=IF($B{r}="","",{ix("grade")})'
    cq[f"G{r}"] = f'=IF($B{r}="","",{ix("total")})'
    cq[f"H{r}"] = f'=IF($B{r}="","",{ix("why")})'
    opener = f'IF({ix("sig")}="No Presence",Templates!$C$20,Templates!$C$17)'
    cq[f"I{r}"] = (f'=IF($B{r}="","",SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE({opener},"{{first_name}}",'
                   f'IF({ix("first")}="",IF({ix("sig")}="No Presence","the practice owner","there"),{ix("first")})),"{{company}}",{ix("company")}),'
                   f'"{{sender_name}}",{S["sender"]}),"{{city}}",{ix("city")}))')
    for col in "ABCDEFGHI":
        cq[f"{col}{r}"].font = f_base; cq[f"{col}{r}"].alignment = wrap; cq[f"{col}{r}"].border = box
    cq.row_dimensions[r].height = 75
for col, w in zip("ABCDEFGHI", [6, 8, 26, 18, 16, 7, 7, 36, 70]):
    cq.column_dimensions[col].width = w
cq.freeze_panes = "C5"

sz = CL["sizeclass"]
ld.conditional_formatting.add(f"{sz}{R1}:{sz}{RN}", FormulaRule(formula=[f'${sz}{R1}="Large"'], fill=PatternFill("solid", bgColor="D9D9D9")))
# interest-level formatting on Leads
it = CL["interest"]
for val, color in [("Hot", "F4B084"), ("Warm", "FFE699"), ("Opted out", "D9D9D9")]:
    ld.conditional_formatting.add(f"{it}{R1}:{it}{RN}", FormulaRule(formula=[f'${it}{R1}="{val}"'], fill=PatternFill("solid", bgColor=color)))


# ---------------------------------------------------------------- Dashboard
db = wb.create_sheet("Dashboard")
put(db, "A1", "Dashboard — is the engine working?", f_title)
put(db, "A2", "All figures recalculate from the Leads tab. Reply/call/proposal counts come from the date columns you fill in.", f_sub)
section(db, 4, "FUNNEL", 3)
for col, t in zip("ABC", ["Stage", "Count", "Conversion"]):
    put(db, f"{col}5", t, f_hdr, grey, border=box)
fun = [
    ("Leads loaded", f'=COUNTA({rng("company")})', None),
    ("Duplicates removed from outreach", f'=COUNTIF({rng("dup")},"DUP")', None),
    ("Valid emails", f'=COUNTIF({rng("estatus")},"Valid")', "=IF(B6=0,\"\",B8/B6)"),
    ("Grade A + B leads", f'=COUNTIF({rng("grade")},"A")+COUNTIF({rng("grade")},"B")', "=IF(B6=0,\"\",B9/B6)"),
    ("Eligible in queue right now", f'=SUM({rng("elig")})', None),
    ("First emails sent", f'=COUNT({rng("sent")})', None),
    ("Replies", f'=COUNT({rng("reply")})', "=IF(B11=0,\"\",B12/B11)"),
    ("Discovery calls", f'=COUNT({rng("call")})', "=IF(B11=0,\"\",B13/B11)"),
    ("Proposals sent", f'=COUNT({rng("prop")})', "=IF(B11=0,\"\",B14/B11)"),
    ("Deals won", f'=COUNT({rng("won")})', "=IF(B11=0,\"\",B15/B11)"),
    ("Revenue won ($)", f'=SUMIFS({rng("value")},{rng("won")},">0")', None),
    ("Follow-ups due today", f'=SUMPRODUCT(--(LEN({rng("fudue")})>0))', None),
]
for i, (lab, fm, conv) in enumerate(fun):
    r = 6 + i
    put(db, f"A{r}", lab, f_bold, border=box)
    put(db, f"B{r}", fm, f_base, fmt='$#,##0;($#,##0);-' if "$" in lab else '#,##0', border=box)
    put(db, f"C{r}", conv, f_base, fmt="0.0%", border=box)
put(db, "D8", "% of loaded", f_note); put(db, "D9", "% of loaded", f_note)
put(db, "D12", "reply rate (of sent)", f_note); put(db, "D13", "call rate (of sent)", f_note)
put(db, "D14", "proposal rate (of sent)", f_note); put(db, "D15", "win rate (of sent)", f_note)

section(db, 19, "DOES THE GRADE PREDICT RESULTS?  (the scoring feedback loop)", 5)
for col, t in zip("ABCDE", ["Grade", "Leads", "Emailed", "Replies", "Calls"]):
    put(db, f"{col}20", t, f_hdr, grey, border=box)
for i, gr in enumerate("ABCD"):
    r = 21 + i
    put(db, f"A{r}", gr, f_bold, border=box)
    put(db, f"B{r}", f'=COUNTIF({rng("grade")},A{r})', f_base, border=box)
    put(db, f"C{r}", f'=COUNTIFS({rng("grade")},A{r},{rng("sent")},">0")', f_base, border=box)
    put(db, f"D{r}", f'=COUNTIFS({rng("grade")},A{r},{rng("reply")},">0")', f_base, border=box)
    put(db, f"E{r}", f'=COUNTIFS({rng("grade")},A{r},{rng("call")},">0")', f_base, border=box)
put(db, "A25", "If A/B don't reply or book more than C/D, retune the point values on Config.", f_note)

section(db, 27, "VALIDATION GATE", 3)
put(db, "A28", "Leads worked (first emails sent)", f_bold, border=box)
put(db, "B28", "=B11", f_base, border=box)
put(db, "C28", f'="of "&{S["g_leads"]}', f_base, border=box)
put(db, "A29", "Discovery calls", f_bold, border=box)
put(db, "B29", "=B13", f_base, border=box)
put(db, "C29", f'="need "&{S["g_calls"]}', f_base, border=box)
put(db, "A30", "Proposals", f_bold, border=box)
put(db, "B30", "=B14", f_base, border=box)
put(db, "C30", f'="need "&{S["g_props"]}', f_base, border=box)
put(db, "A31", "Verdict", f_bold, border=box)
put(db, "B31", (f'=IF(B28<{S["g_leads"]},"IN PROGRESS — "&B28&" of "&{S["g_leads"]}&" worked",'
                f'IF(AND(B29>={S["g_calls"]},B30>={S["g_props"]}),"GATE MET — build the real system",'
                f'"NOT MET — change the offer or the signal, then rerun"))'), f_bold, border=box)
db.merge_cells("B31:C31")

section(db, 33, "BUDGET", 3)
put(db, "A34", "Spent so far", f_bold, border=box)
put(db, "B34", f'={S["spent"]}', f_base, fmt='$#,##0;($#,##0);-', border=box)
put(db, "A35", "Remaining of cap", f_bold, border=box)
put(db, "B35", f'={S["remaining"]}', f_base, fmt='$#,##0;($#,##0);-', border=box)
put(db, "A36", "Cost per discovery call", f_bold, border=box)
put(db, "B36", '=IF(B13=0,"n/a",B34/B13)', f_base, fmt='$#,##0;($#,##0);-', border=box)
section(db, 38, "INTEREST LEVEL (engagement with your digital properties)", 3)
for i, lab in enumerate(["Hot", "Warm", "Cold", "No contact yet", "Opted out"]):
    r = 39 + i
    put(db, f"A{r}", lab, f_bold, border=box)
    put(db, f"B{r}", f'=COUNTIF({rng("interest")},A{r})', f_base, border=box)
put(db, "A44", "Interest is scored from the Events tab, so these stay at 'No contact yet' until you log events.", f_note)
section(db, 46, "BEST CHANNEL MIX", 3)
for i, lab in enumerate(["Email", "Phone", "Find contact"]):
    r = 47 + i
    put(db, f"A{r}", lab, f_bold, border=box)
    put(db, f"B{r}", f'=COUNTIF({rng("channel")},A{r})', f_base, border=box)
for col, w in zip("ABCDE", [40, 26, 18, 24, 10]):
    db.column_dimensions[col].width = w

# ---------------------------------------------------------------- START HERE
st = wb.create_sheet("START HERE", 0)
st.column_dimensions["A"].width = 118
lines = [
    ("Lead Engine — validation template", "title"),
    ("Goal: prove, in about 3 weeks and under $100, that signal-based outreach books discovery calls for your 72-hour website offer. "
     "Only then build the code.", "sub"),
    ("", None),
    ("1. SET UP (30 minutes, once)", "h"),
    ("• Config tab: fill in your name, business, postal address (required by CAN-SPAM), and pick 1–2 verticals and 2–3 metros.", None),
    ("• Leads tab, row 2 is an EXAMPLE. Clear its blue cells (columns A–T and the Status column) before loading real leads.", None),
    ("• Templates tab: tweak the email wording. The drafts on Leads and Queue update instantly.", None),
    ("• Buy a lookalike sending domain + one mailbox TODAY and start warm-up — it takes ~2 weeks, the slowest step.", None),
    ("", None),
    ("2. THE PIPELINE (column colors on the Leads tab)", "h"),
    ("Collect (blue) → Enrich (green) → Validate (yellow) → Clean (grey, automatic) → Score (orange, automatic) → "
     "Outreach (purple, automatic) → Track (blue)", None),
    ("• Collect: paste leads in from Indeed job postings, Google Maps/Outscraper exports, directories. Hiring postings are your strongest signal.", None),
    ("• Enrich: add decision-maker name, title, email, LinkedIn. Add Mobile PageSpeed (free at pagespeed.web.dev) and Outdated Site Y/N.", None),
    ("• Validate: run emails through a verifier (e.g. MillionVerifier), then set Email Status to Valid / Risky / Invalid.", None),
    ("• Clean, Score, Outreach: formulas. Dedupe Key flags DUP; Total/Grade rank the lead; Draft Subject and Draft Email 1 are written for you.", None),
    ("• Track: set Status, First Sent Date, Follow-ups Sent, Reply / Call / Proposal / Won dates. The Dashboard reads these.", None),
    ("", None),
    ("3. YOUR 2-HOUR DAILY ROUTINE", "h"),
    ("• 0:00–0:25  Load new leads (paste Indeed / Maps rows; Claude can do the collecting in a session and hand you rows to paste).", None),
    ("• 0:25–0:45  Verify emails, set Email Status.", None),
    ("• 0:45–1:15  Open Queue. Read each draft. Fix the first line if it's off. Run Lead Engine ▸ Create Gmail drafts (optional script).", None),
    ("• 1:15–1:35  Gmail ▸ Drafts: read, tweak, send up to the daily cap. YOU press send.", None),
    ("• 1:35–1:55  Follow-ups due (Leads, Follow-Up Due column), replies, and 5–10 manual calls or LinkedIn notes to A-grade leads.", None),
    ("• 1:55–2:00  Update Status and dates. Glance at Dashboard.", None),
    ("", None),
    ("4. GUARDRAILS", "h"),
    ("• Email: B2B cold email is allowed in the US under CAN-SPAM only with a real postal address, honest sender info, and a working opt-out. "
     "The templates include these. Honor every 'no thanks' by setting Status to Do Not Contact.", None),
    ("• Phone: dial by hand, business lines only. No autodialers or prerecorded messages. Check sole proprietors' numbers against the Do Not Call registry.", None),
    ("• LinkedIn: manual only. Automation tools violate LinkedIn's terms and could cost you your job-search profile.", None),
    ("• WhatsApp: warm leads only (after they reply or share a WhatsApp number). Cold WhatsApp messages break its business policy.", None),
    ("• Data sources: use official APIs or licensed vendors for Google Maps and review sites; scraping them directly violates their terms. "
     "This is not legal advice; have a lawyer review before you sell leads or scale.", None),
    ("", None),
    ("5. LOCAL BUSINESSES WITH NO WEB PRESENCE (e.g. NJ medical offices)", "h"),
    ("• Source: the CMS NPI Registry gives practice name, phone, specialty and an authorized official. It has no emails. "
     "Run: python3 -m leadengine run --source nppes --state NJ", None),
    ("• Presence check: set Website Present / Google Profile Present to N only after a search or Places lookup confirms it. "
     "Those two columns drive the No Presence signal and the Urgency points (Config rows 85–89).", None),
    ("• No email? Use the Call Queue tab (phone opener included) or the postcard copy on Templates. Cold email needs a verified address.", None),
    ("• Advertising copy for a physician client must follow NJ rules (N.J.A.C. 13:35-6.10). Get legal review; this is not legal advice.", None),
    ("", None),
    ("6. INTEREST LEVEL (Hot / Warm / Cold) = how they engage with YOUR properties", "h"),
    ("• Log clicks, site visits, form fills, replies and bookings on the Events tab using the lead's Dedupe Key. "
     "Config rows 92–106 hold the window, thresholds and points. Unsubscribed flips the lead to Opted out.", None),
    ("• Add ?utm_source=leadengine&utm_content=<Dedupe Key> to every link you send so visits can be matched back to the lead.", None),
    ("• Email opens are inflated by image pre-loading (Apple Mail and others), so they score only 1 point.", None),
    ("", None),
    ("7. THE GATE", "h"),
    ("After ~100 first emails: at least 2 discovery calls and 1 proposal means build the real system. Otherwise change ONE thing — the offer, "
     "the signal, or the subject line — and run another 100. See Dashboard ▸ Validation Gate.", None),
    ("", None),
    ("Legend: blue text = input you type · yellow fill = Config setting · black text = formula (do not overwrite).", "sub"),
]
for i, (txt, kind) in enumerate(lines):
    r = i + 1
    cell = st[f"A{r}"]
    cell.value = txt
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    if kind == "title": cell.font = f_title
    elif kind == "sub": cell.font = f_sub
    elif kind == "h":
        cell.font = f_white; cell.fill = dark
    else: cell.font = f_base

wb._sheets = [wb["START HERE"], wb["Config"], wb["Leads"], wb["Queue"], wb["Call Queue"], wb["Events"], wb["Dashboard"], wb["Templates"]]
wb.active = 0
wb.save(OUT)
print("saved", OUT)
