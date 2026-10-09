import csv
import os

FIELDS = [("source", "Source"), ("company", "Company"), ("website", "Website"), ("phone", "Phone"), ("city", "City"),
          ("state", "State"), ("vertical", "Vertical"), ("specialty", "Specialty"), ("npi", "NPI"), ("emp", "Employees (est.)"), ("hiring", "Hiring Signal (Y/N)"),
          ("expand", "Expansion Signal (Y/N)"), ("detail", "Signal Detail"), ("sigdate", "Signal Date"),
          ("first", "First Name"), ("last", "Last Name"), ("title", "Title"), ("email", "Email"),
          ("linkedin", "LinkedIn URL"), ("psi", "Mobile PageSpeed (0-100)"), ("outdated", "Outdated Site (Y/N)"), ("hasweb", "Website Present (Y/N)"), ("hasgbp", "Google Profile Present (Y/N)"), ("reviews", "Review Count"), ("providers", "Providers (est.)"), ("sizeov", "Size Override"),
          ("estatus", "Email Status"), ("status", "Status"), ("notes", "Notes")]
EXTRA = [("size_class", "Size Class"), ("strength", "Signal Strength"), ("total", "Score"), ("grade", "Grade"), ("why", "Why This Lead"),
         ("signal", "Primary Signal"), ("next_step", "Next Step"), ("subject", "Draft Subject"), ("body", "Draft Email 1")]


def write_csv(path, leads):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([h for _, h in FIELDS + EXTRA])
        for ld in leads:
            w.writerow([("" if ld.get(k) is None else ld.get(k)) for k, _ in FIELDS + EXTRA])


def write_workbook(template, path, leads, cfg=None, cities=(), industry=""):
    """Fill a copy of the Sheets template. Only input columns are written, so every formula keeps working."""
    from openpyxl import load_workbook
    wb = load_workbook(template)
    ws = wb["Leads"]
    col = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
    cf = wb["Config"]                                       # keep the sheet's scoring in step with this run
    if cfg:
        for row, key in ((4, "name"), (5, "business"), (6, "address"), (7, "portfolio_url"), (8, "booking_link"), (9, "offer")):
            cf.cell(row=row, column=2).value = cfg["sender"][key]
        cf["B108"] = cfg["sender"].get("tracker_base", "")
        cf["B109"] = cfg["sender"].get("link_mode", "plain")
        cf["B112"], cf["B113"] = cfg["size"]["small_max"], cfg["size"]["medium_max"]
        cf["B114"] = "Y" if cfg.get("exclude_large") else "N"
        cf["B12"], cf["B13"] = cfg["target"]["employees_min"], cfg["target"]["employees_max"]
    for i in range(10):
        cf.cell(row=28 + i, column=1).value = cities[i] if i < len(cities) else None
    for i in range(40):                                     # overflow list in column E (rows 28-67)
        cf.cell(row=28 + i, column=5).value = cities[10 + i] if 10 + i < len(cities) else None
    if industry:
        for i in range(10):
            cf.cell(row=16 + i, column=1).value = industry if i == 0 else None
    for r in range(2, ws.max_row + 1):                      # clear example/old inputs
        for _, h in FIELDS:
            ws.cell(row=r, column=col[h]).value = None
    for i, ld in enumerate(leads):
        for k, h in FIELDS:
            v = ld.get(k)
            if k == "notes":
                v = f"{ld.get('strength', '')}. " + (ld.get("notes") or "")
            ws.cell(row=2 + i, column=col[h]).value = v if v != "" else None
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
