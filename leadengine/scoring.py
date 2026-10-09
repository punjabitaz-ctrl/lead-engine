"""Same 100-point model as the Leads tab. A lead is a dict keyed like the sheet (see export.FIELDS)."""
import datetime as dt


def score(lead, cfg, query_verticals=(), today=None):
    today = today or dt.date.today()
    p, t, tg = cfg["points"], cfg["thresholds"], cfg["target"]
    fit = 0
    if lead.get("vertical") and (not query_verticals or lead["vertical"].lower() in [v.lower() for v in query_verticals]):
        fit += p["vertical"]
    emp = lead.get("emp")
    if isinstance(emp, (int, float)) and tg["employees_min"] <= emp <= tg["employees_max"]:
        fit += p["size"]
    if lead.get("city"):
        fit += p["metro"]
    urg = p["hiring"] if lead.get("hiring") == "Y" else 0
    psi = lead.get("psi")
    if isinstance(psi, (int, float)):
        urg += p["psi_poor"] if psi < t["psi_poor"] else p["psi_moderate"] if psi < t["psi_moderate"] else 0
    urg += p["outdated"] if lead.get("outdated") == "Y" else 0
    urg += p["expansion"] if lead.get("expand") == "Y" else 0
    reach = {"Valid": p["email_valid"], "Risky": p["email_risky"]}.get(lead.get("estatus"), 0)
    reach += p["phone"] if lead.get("phone") else 0
    reach += p["linkedin"] if lead.get("linkedin") else 0
    fresh = 0
    if lead.get("sigdate"):
        age = (today - lead["sigdate"]).days
        fresh = p["fresh1"] if age <= t["fresh1_days"] else p["fresh2"] if age <= t["fresh2_days"] else 0
    total = fit + urg + reach + fresh
    grade = "A" if total >= t["grade_a"] else "B" if total >= t["grade_b"] else "C" if total >= t["grade_c"] else "D"
    return {"fit": fit, "urg": urg, "reach": reach, "fresh": fresh, "total": total, "grade": grade}


def primary_signal(lead, cfg):
    if lead.get("hiring") == "Y":
        return "Hiring"
    psi = lead.get("psi")
    if (isinstance(psi, (int, float)) and psi < cfg["thresholds"]["psi_poor"]) or lead.get("outdated") == "Y":
        return "Weak Site"
    return "Expansion" if lead.get("expand") == "Y" else "General"


def tier(lead, cfg, today=None):
    """Interest level: hot = fresh hiring signal (or several postings); warm = within 90 days; cold = anything else."""
    today = today or dt.date.today()
    i = cfg["interest"]
    if lead.get("hiring") != "Y" and lead.get("outdated") != "Y":
        return "cold"
    age = (today - lead["sigdate"]).days if lead.get("sigdate") else 9999
    if lead.get("hiring") == "Y" and (age <= i["hot_days"] or lead.get("n_postings", 1) >= i["hot_min_postings"]):
        return "hot"
    if age <= i["warm_days"] or lead.get("outdated") == "Y":
        return "warm"
    return "cold"


def why(lead):
    parts = []
    if lead.get("detail"):
        parts.append(lead["detail"] + ".")
    if isinstance(lead.get("psi"), (int, float)):
        parts.append(f"Mobile PageSpeed {lead['psi']}/100.")
    if lead.get("outdated") == "Y":
        parts.append("Site looks outdated.")
    parts.append({"Valid": "Email verified.", "Risky": "Email risky."}.get(lead.get("estatus"), "No verified email."))
    return " ".join(parts)
