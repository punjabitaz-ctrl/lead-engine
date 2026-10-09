"""Build the review-checklist workbooks from data/candidates/*.csv. Usage: python3 tools/build_review.py lists/"""
import csv, os, sys, urllib.parse
from collections import Counter
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else "lists"
STAMP = "2026-10-09"
SEGMENTS = [("cardiology", "Cardiology"), ("ophthalmology", "Ophthalmology"), ("pt", "Physical therapy"),
            ("dentist", "Dentist"), ("mental_health", "Mental health")]


def F(**k):
    b = {"name": "Arial", "size": 10}
    b.update(k)
    return Font(**b)


thin = Side(style="thin", color="BFBFBF")
box = Border(left=thin, right=thin, top=thin, bottom=thin)
hdrfill = PatternFill("solid", fgColor="1F3864")
inp = PatternFill("solid", fgColor="FFFF99")
wrap = Alignment(wrap_text=True, vertical="top")
PRI = {"High": "F8CBAD", "Medium": "FFE699", "Low": "C6E0B4"}


def size_class(r):
    if r["size_override"]:
        return r["size_override"]
    try:
        n = int(r["providers"])
    except ValueError:
        return "Unknown"
    return "Solo" if n <= 1 else "Small" if n <= 5 else "Medium" if n <= 15 else "Large"


def links(name, city):
    q = urllib.parse.quote_plus(f'"{name}" {city} NJ')
    return f"https://www.google.com/search?q={q}", f"https://www.google.com/maps/search/{q}"


def load(name):
    with open(f"data/candidates/{name}.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def sheet(ws, title, rows):
    ws.title = title[:31]
    ws["A1"] = title
    ws["A1"].font = F(bold=True, size=14)
    ws["A2"] = ("Blue on yellow = you fill in. About 30 seconds a row using the two links. Decision: Keep / Drop / Unsure. Filter the Size column to hide Large groups; "
                "'Size basis' says whether a size is evidence or a suspicion. Nothing here is verified: it comes from directory listings found by web search on 2026-10-09.")
    ws["A2"].font = F(italic=True, color="595959")
    ws["A2"].alignment = wrap
    ws.merge_cells("A2:T2")
    ws.row_dimensions[2].height = 32
    H = ["#", "Review priority", "Practice", "Specialty", "Town", "Address", "Phone", "Size", "Size basis", "What to verify", "Why flagged", "Google search", "Google Maps",
         "Website? (Y/N)", "Google profile claimed? (Y/N)", "Review count", "Independent? (Y/N/Unsure)", "Providers (count)", "Decision", "Your notes"]
    for i, h in enumerate(H, 1):
        c = ws.cell(row=4, column=i, value=h)
        c.font = F(bold=True, color="FFFFFF")
        c.fill = hdrfill
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = box
    ws.row_dimensions[4].height = 34
    ex = ["EX", "Low", "EXAMPLE Practice LLC (delete this row)", "Example", "Edison", "1 Main St", "732-555-0100", "Small", "Evidence: 3 clinicians", "(example)", "(example)", "", "",
          "Y", "Y", 42, "Y", 3, "Keep", "Owner-run; site is dated"]
    for i, v in enumerate(ex, 1):
        c = ws.cell(row=5, column=i, value=v)
        c.font = F(italic=True, color="808080")
        c.alignment = wrap
        c.border = box
    order = {"High": 0, "Medium": 1, "Low": 2}
    r = 6
    for row in sorted(rows, key=lambda x: (x["subspecialty"], order.get(x["review"], 1), x["city"], x["practice"])):
        s, m = links(row["practice"], row["city"])
        sc = size_class(row)
        vals = [r - 5, row["review"], row["practice"], row["subspecialty"], row["city"], row["address"], row["phone"], sc, row["size_basis"], row["check"], row["evidence"]]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.font = F(bold=(i == 3))
            c.alignment = wrap
            c.border = box
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=PRI.get(row["review"], "FFE699"))
        if sc in ("Large", "Medium"):
            suspected = row["size_basis"].startswith("Suspected")
            ws.cell(row=r, column=8).fill = PatternFill("solid", fgColor=("F2F2F2" if suspected else "D9D9D9") if sc == "Large" else "EDEDED")
        for col, u, label in ((12, s, "Search"), (13, m, "Maps")):
            c = ws.cell(row=r, column=col, value=f'=HYPERLINK("{u}","{label}")')
            c.font = F(color="0563C1", underline="single")
            c.border = box
        for col in range(14, 21):
            c = ws.cell(row=r, column=col)
            c.fill = inp
            c.font = F(color="0000FF")
            c.border = box
            c.alignment = wrap
        ws.row_dimensions[r].height = 70
        r += 1
    for f1, rng in (('"Y,N"', f"N6:O{r}"), ('"Y,N,Unsure"', f"Q6:Q{r}"), ('"Keep,Drop,Unsure"', f"S6:S{r}")):
        dv = DataValidation(type="list", formula1=f1, allow_blank=True)
        dv.add(rng)
        ws.add_data_validation(dv)
    ws.auto_filter.ref = f"A4:T{max(r - 1, 5)}"
    for col, w in zip("ABCDEFGHIJKLMNOPQRST", [4, 10, 32, 20, 16, 26, 14, 9, 30, 50, 40, 9, 9, 10, 12, 9, 14, 10, 10, 32]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "D5"


def build(seg, label):
    practices, individuals = load(f"{seg}_practices"), load(f"{seg}_individuals")
    wb = Workbook()
    ov = wb.active
    ov.title = "Overview"
    subs = sorted({r["subspecialty"] for r in practices})
    ov["A1"] = f"{label}: Middlesex and Somerset counties, NJ ({STAMP})"
    ov["A1"].font = F(bold=True, size=14)
    heads = ["Specialty", "Practices", "Individual clinicians", "Large", "Medium", "Unknown size", "High-priority reviews"]
    for i, h in enumerate(heads, 1):
        c = ov.cell(row=3, column=i, value=h)
        c.font = F(bold=True, color="FFFFFF")
        c.fill = hdrfill
        c.border = box
    allsubs = sorted({r["subspecialty"] for r in practices + individuals})
    for k, sub in enumerate(allsubs, 4):
        p = [r for r in practices if r["subspecialty"] == sub]
        ind = [r for r in individuals if r["subspecialty"] == sub]
        sizes = Counter(size_class(r) for r in p)
        vals = [sub, len(p), len(ind), sizes["Large"], sizes["Medium"], sizes["Unknown"], sum(1 for r in p + ind if r["review"] == "High")]
        for i, v in enumerate(vals, 1):
            c = ov.cell(row=k, column=i, value=v)
            c.font = F()
            c.border = box
    n = 4 + len(allsubs)
    ov.cell(row=n, column=1, value="Total").font = F(bold=True)
    for col in range(2, 8):
        c = ov.cell(row=n, column=col, value=f"=SUM({chr(64 + col)}4:{chr(64 + col)}{n - 1})")
        c.font = F(bold=True)
    notes = ["Every row is unverified. Start with the High-priority rows, then Medium, then Low.",
             "Size: Large and Medium are marked only where there is evidence or a stated suspicion (see 'Size basis'); Unknown is not the same as small.",
             "Individuals are kept on their own sheet; ownership is the main unknown for them.",
             "Hospital- and system-owned sites were excluded from the lists."]
    for i, t in enumerate(notes, n + 2):
        c = ov.cell(row=i, column=1, value=t)
        c.font = F(italic=True, color="595959")
    for col, w in zip("ABCDEFG", [34, 10, 20, 8, 8, 12, 20]):
        ov.column_dimensions[col].width = w
    for sub in subs:
        p = [r for r in practices if r["subspecialty"] == sub]
        sheet(wb.create_sheet(), f"{sub[:22]} ({len(p)})", p)
    sheet(wb.create_sheet(), f"Individuals ({len(individuals)})", individuals)
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"NJ_{seg}_review_{STAMP}.xlsx")
    wb.save(out)
    print("built", out)


for seg, label in SEGMENTS:
    build(seg, label)
