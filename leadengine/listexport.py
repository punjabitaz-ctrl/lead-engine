"""Export a lead list to CSV, Excel (.xlsx) or PDF, using only the standard library.

  leadengine campaign export <name> [--list approved|pending|rejected|review|all|FILE] --format csv|xlsx|pdf
                                    [--columns contact|full|"Company,Email,..."] [--grade A,B] [--min-score N]
                                    [--min-confidence N] [--email-status Valid,Risky] [--has-email] [--include-suppressed] [--out PATH]
  leadengine export FILE.csv --format csv|xlsx|pdf [same options]

Suppressed leads (opt-outs, bounces, do-not-contact) are left out of a campaign export unless --include-suppressed.
CSV cells that start with = + - @ get a leading apostrophe so a spreadsheet never runs them as formulas.
The Excel file has a frozen, filterable header row and an About sheet with the filters and counts.
The PDF is a landscape table for reading or printing; long cells are cut with "..." (the CSV and Excel keep everything)."""
import csv
import datetime as dt
import os
import re
import zipfile
from xml.sax.saxutils import escape

from . import campaign

CONTACT = ["Company", "First Name", "Last Name", "Title", "Email", "Email Status", "Phone", "Website", "City", "State", "Vertical",
           "Specialty", "Score", "Grade", "Primary Signal", "Why This Lead", "Confidence", "Issues", "Last Verified"]
PDF_DEFAULT = ["Company", "First Name", "Last Name", "Title", "Email", "Email Status", "Phone", "City", "State", "Grade", "Score",
               "Confidence", "Primary Signal"]
INTERNAL = {"Draft Email 1", "Draft Subject", "Lead Key", "Decision", "Reviewer Notes", "Checked"}
NUMERIC = {"Score", "Confidence", "Review Count", "Employees (est.)", "Providers (est.)", "Mobile PageSpeed (0-100)"}
PDF_MAX_COLUMNS = 16
FORMULA = ("=", "+", "-", "@", "\t", "\r")
NOTE = ("Business contact data compiled from public sources. Email Status Valid means a mailbox check passed; Risky means published on "
        "the business's site but not checked; Unverified means not checked. Confirm before you rely on it.")


# ---- selecting rows and columns --------------------------------------------------
def load(name, root, which):
    """-> (rows, label). Rows from a campaign list or a CSV path; review packs are read together."""
    from .enrich import list_paths
    if name is None:
        rows, _ = campaign._read_csv(which)
        return rows, os.path.basename(which)
    rows, seen = [], set()
    for path in list_paths(name, root, which):
        for r in campaign._read_csv(path)[0]:
            k = campaign.lead_key(r)
            if k not in seen:                    # the same lead can sit in a pack and in approved.csv
                seen.add(k)
                rows.append(r)
    return rows, which if which in ("approved", "pending", "rejected", "review", "all") else os.path.basename(which)


def columns(spec, rows, fmt):
    have = list(dict.fromkeys(k for r in rows for k in r))
    if spec in (None, ""):
        spec = "pdf" if fmt == "pdf" else "contact"
    if spec == "full":
        cols = [c for c in have if c not in INTERNAL]
    elif spec in ("contact", "pdf"):
        cols = [c for c in (CONTACT if spec == "contact" else PDF_DEFAULT) if c in have]
    else:
        cols = [c.strip() for c in spec.split(",") if c.strip()]
        missing = [c for c in cols if c not in have]
        if missing:
            raise SystemExit(f"Not in this list: {', '.join(missing)}. Columns it has: {', '.join(have)}")
    if not cols:
        raise SystemExit("None of the chosen columns are in this list")
    return cols


def _num(v):
    try:
        return float(str(v).strip())
    except ValueError:
        return None


def select(rows, grade=None, min_score=None, min_confidence=None, email_status=None, has_email=False, sup=None):
    """-> (kept rows, {reason: count left out})"""
    kept, out = [], {}
    def drop(why):
        out[why] = out.get(why, 0) + 1
    for r in rows:
        if sup and campaign.suppressed(r, sup):
            drop("suppressed (opt-out, bounce or do-not-contact)")
        elif grade and (r.get("Grade") or "").strip().upper() not in grade:
            drop("grade")
        elif min_score is not None and (_num(r.get("Score")) or 0) < min_score:
            drop("score below minimum")
        elif min_confidence is not None and (_num(r.get("Confidence")) if _num(r.get("Confidence")) is not None else -1) < min_confidence:
            drop("confidence below minimum (or not checked; run campaign enrich)")
        elif email_status and (r.get("Email Status") or "").strip() not in email_status:
            drop("email status")
        elif has_email and not (r.get("Email") or "").strip():
            drop("no email")
        else:
            kept.append(r)
    return kept, out


# ---- CSV -----------------------------------------------------------------------
def _safe(v):
    v = "" if v is None else str(v)
    return "'" + v if v.startswith(FORMULA) else v


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:      # the BOM lets Excel read accents correctly
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([_safe(r.get(c, "")) for c in cols])


# ---- XLSX (Office Open XML written by hand) ---------------------------------------------
_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _x(v):
    return escape(_BAD_XML.sub("", str(v))[:32000], {'"': "&quot;"})


def _col(i):
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def _cell(ref, value, style=0, numeric=False):
    st = f' s="{style}"' if style else ""
    if value in (None, ""):
        return f'<c r="{ref}"{st}/>' if style else ""
    n = _num(value) if numeric else None
    if n is not None:
        return f'<c r="{ref}"{st}><v>{int(n) if n == int(n) else n}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{_x(value)}</t></is></c>'


def _sheet(table, widths=None, header=True):
    """table: list of rows (lists). -> worksheet XML."""
    last = _col(max(len(r) for r in table) - 1) + str(len(table))
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">', f'<dimension ref="A1:{last}"/>']
    if header:
        out.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                   '</sheetView></sheetViews>')
    if widths:
        out.append("<cols>" + "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths)) + "</cols>")
    out.append("<sheetData>")
    for y, row in enumerate(table, 1):
        cells = "".join(_cell(f"{_col(x)}{y}", v, 1 if (header and y == 1) else 0, numeric=(header and y > 1 and table[0][x] in NUMERIC))
                        for x, v in enumerate(row))
        out.append(f'<row r="{y}">{cells}</row>')
    out.append("</sheetData>")
    if header and len(table) > 1:
        out.append(f'<autoFilter ref="A1:{last}"/>')
    out.append("</worksheet>")
    return "".join(out)


def write_xlsx(path, rows, cols, about):
    table = [cols] + [[r.get(c, "") for c in cols] for r in rows]
    widths = [min(60, max(8, max(len(str(t[i])) for t in table[:500]) + 2)) for i in range(len(cols))]
    about_rows = [["About this export", ""]] + [[k, v] for k, v in about]
    sheets = [("Leads", _sheet(table, widths)), ("About", _sheet(about_rows, [24, 100], header=False))]
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for i in range(1, len(sheets) + 1)) + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1)) + "</sheets>"
          + (f'<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Leads!$A$1:${_col(len(cols) - 1)}${len(table)}</definedName></definedNames>'
             if len(table) > 1 else "") + "</workbook>")
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                        for i in range(1, len(sheets) + 1))
              + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
              '<fill><patternFill patternType="solid"><fgColor rgb="FFDCE6F1"/><bgColor indexed="64"/></patternFill></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wbrels)
        z.writestr("xl/styles.xml", styles)
        for i, (_, xml) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)


# ---- PDF (PDF 1.4, the built-in Helvetica fonts) ------------------------------------------
# Helvetica advance widths for ASCII 32-126, in 1/1000 em (from the standard AFM). Anything else counts as 556.
_W = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + [
    278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667,
    611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833,
    556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]


def text_width(s, size, bold=False):
    w = sum(_W[ord(ch) - 32] if 32 <= ord(ch) <= 126 else 556 for ch in s)
    return w * size / 1000 * (1.06 if bold else 1.0)


def fit(s, width, size, bold=False):
    s = " ".join(str(s or "").split())
    if text_width(s, size, bold) <= width:
        return s
    while s and text_width(s + "...", size, bold) > width:
        s = s[:-1]
    return (s.rstrip() + "...") if s else ""


def _pdf_str(s):
    b = s.encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def write_pdf(path, rows, cols, title, note=NOTE, size=7.5):
    W, H, M = 792, 612, 36                              # US Letter, landscape
    dropped = []
    if len(cols) > PDF_MAX_COLUMNS:
        cols, dropped = cols[:PDF_MAX_COLUMNS], cols[PDF_MAX_COLUMNS:]
    pad, row_h = 3, size + 4
    avail = W - 2 * M
    nat = []
    for c in cols:
        vals = sorted(text_width(" ".join(str(r.get(c, "")).split()), size) for r in rows[:1000]) or [0]
        p90 = vals[int(len(vals) * 0.9) - 1 if len(vals) > 1 else 0]
        nat.append(min(170, max(text_width(c, size, True), p90, 24) + 2 * pad))
    if sum(nat) > avail:                                # narrow columns (phone, state, grade) keep their width; wide ones give way
        fixed = sum(n for n in nat if n <= 70)
        wide = sum(n for n in nat if n > 70)
        k = max(0.2, (avail - fixed) / wide) if wide else 1
        nat = [n if n <= 70 else max(40, n * k) for n in nat]
    widths = [n * avail / sum(nat) for n in nat]
    top = H - M - 30
    per_page = max(1, int((top - (M + 24)) // row_h) - 1)
    pages = [rows[i:i + per_page] for i in range(0, len(rows), per_page)] or [[]]
    stamp = dt.date.today().isoformat()
    streams = []
    for n, chunk in enumerate(pages, 1):
        ops = []
        def text(x, y, s, font="F1", sz=size):
            ops.append(b"BT /%s %.1f Tf %.2f %.2f Td (%s) Tj ET" % (font.encode(), sz, x, y, _pdf_str(s)))
        text(M, H - M - 10, fit(title, avail * 0.75, 11, True), "F2", 11)
        right = f"{stamp}   page {n} of {len(pages)}"
        text(W - M - text_width(right, 8), H - M - 10, right, "F1", 8)
        y = top
        ops.append(b"0.86 0.90 0.95 rg %.2f %.2f %.2f %.2f re f 0 g" % (M, y - 3, avail, row_h))
        x = M
        for c, w in zip(cols, widths):
            text(x + pad, y, fit(c, w - 2 * pad, size, True), "F2")
            x += w
        for i, r in enumerate(chunk):
            y -= row_h
            if i % 2:
                ops.append(b"0.96 0.96 0.96 rg %.2f %.2f %.2f %.2f re f 0 g" % (M, y - 3, avail, row_h))
            x = M
            for c, w in zip(cols, widths):
                text(x + pad, y, fit(r.get(c, ""), w - 2 * pad, size))
                x += w
        foot = note + (f" Not shown here: {', '.join(dropped)} (in the CSV and Excel exports)." if dropped else "")
        for k, line in enumerate(_wrap(foot, avail, 6.5)[:3]):
            text(M, M - 4 + 8 * (2 - k), line, "F1", 6.5)
        streams.append(b"\n".join(ops))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            b"<< /Producer (leadengine) /Title (%s) >>" % _pdf_str(title)]
    kids = []
    for s in streams:
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(s), s))
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>"
                    % (W, H, len(objs)))
        kids.append(len(objs))
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    out, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 5 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return {"pages": len(pages), "columns_left_out": dropped}


def _wrap(s, width, size):
    lines, cur = [], ""
    for word in s.split():
        if cur and text_width(cur + " " + word, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


# ---- the command ------------------------------------------------------------------
def export(rows, fmt, out, cols, title, about):
    if fmt == "csv":
        write_csv(out, rows, cols)
        return {}
    if fmt == "xlsx":
        write_xlsx(out, rows, cols, about)
        return {}
    if fmt == "pdf":
        return write_pdf(out, rows, cols, title)
    raise SystemExit(f"Unknown format {fmt!r}: choose csv, xlsx or pdf")


def main(argv, root=campaign.ROOT, campaign_mode=True):
    import argparse
    ap = argparse.ArgumentParser(prog="leadengine campaign export" if campaign_mode else "leadengine export",
                                 description="Export a lead list to CSV, Excel or PDF.")
    ap.add_argument("name" if campaign_mode else "file")
    if campaign_mode:
        ap.add_argument("--list", default="approved", help="approved, pending, rejected, review (every pack), all, or a CSV path")
    ap.add_argument("--format", required=True, choices=["csv", "xlsx", "pdf"])
    ap.add_argument("--columns", help='contact (default), full, or a comma list like "Company,Email,Phone"')
    ap.add_argument("--grade", help="keep these grades, e.g. A,B")
    ap.add_argument("--min-score", type=float)
    ap.add_argument("--min-confidence", type=float, help="needs campaign enrich first")
    ap.add_argument("--email-status", help="keep these statuses, e.g. Valid,Risky")
    ap.add_argument("--has-email", action="store_true")
    if campaign_mode:
        ap.add_argument("--include-suppressed", action="store_true", help="keep opt-outs, bounces and do-not-contact (not for outreach)")
    ap.add_argument("--out", help="output path (default: the campaign's exports/ folder, or next to the file)")
    a = ap.parse_args(argv)
    if campaign_mode:
        campaign.load(a.name, root)
        rows, label = load(a.name, root, a.list)
        sup = None if a.include_suppressed else campaign.load_suppressions(a.name, root)
        title_name = a.name
    else:
        if not os.path.exists(a.file):
            raise SystemExit(f"No such file: {a.file}")
        rows, label = load(None, root, a.file)
        sup, title_name = None, os.path.splitext(os.path.basename(a.file))[0]
    total = len(rows)
    split = lambda s: {x.strip() for x in s.split(",") if x.strip()} if s else None
    rows, left_out = select(rows, {g.upper() for g in split(a.grade)} if a.grade else None, a.min_score, a.min_confidence,
                            split(a.email_status), a.has_email, sup)
    if not rows:
        raise SystemExit(f"Nothing to export: {total} rows, all left out ({', '.join(f'{k} {v}' for k, v in left_out.items()) or 'list is empty'})")
    cols = columns(a.columns, rows, a.format)
    today = dt.date.today().isoformat()
    if a.out:
        out = a.out
    elif campaign_mode:
        d = os.path.join(campaign.folder(a.name, root), "exports")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, f"{a.name}-{re.sub(r'[^A-Za-z0-9_-]+', '-', label)}-{today}.{a.format}")
    else:
        out = os.path.splitext(a.file)[0] + f"-export.{a.format}"
    filters = ", ".join(f"{k} {v}" for k, v in [("grade", a.grade), ("min score", a.min_score), ("min confidence", a.min_confidence),
                                                ("email status", a.email_status), ("has email", a.has_email or None)] if v) or "none"
    about = [("Campaign" if campaign_mode else "File", title_name), ("List", label), ("Exported", today), ("Rows exported", len(rows)),
             ("Rows in list", total), ("Left out", ", ".join(f"{k}: {v}" for k, v in left_out.items()) or "none"), ("Filters", filters),
             ("Data note", NOTE)]
    title = f"{title_name}: {label} leads ({len(rows)})"
    info = export(rows, a.format, out, cols, title, about)
    if campaign_mode:
        campaign.log(a.name, "export", root, list=a.list, format=a.format, rows=len(rows), out=out)
    print(f"Wrote {len(rows)} of {total} rows to {out}" + (f" ({info['pages']} pages)" if info.get("pages") else ""))
    for k, v in left_out.items():
        print(f"  left out, {k}: {v}")
    if info.get("columns_left_out"):
        print(f"  the PDF fits {PDF_MAX_COLUMNS} columns; not shown: {', '.join(info['columns_left_out'])}")
    return 0
