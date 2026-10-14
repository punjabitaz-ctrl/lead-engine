"""Practice site builder: a client's intake (JSON) -> a finished 1-page or 3-page static site, plus a QA check.

  python3 -m leadengine site build intake.json --out site/ [--pages 1|3]
  python3 -m leadengine site qa site/

The same builder makes the paid sites and the free mock-ups for top leads, so delivery is mostly filling in an intake. No external requests are made by
the generated pages (inline CSS, system fonts, local images only). The contact form never asks for health details and tells visitors not to send any."""
import html
import json
import os
import re
import shutil

REQUIRED = ["practice_name", "phone", "address", "city", "state", "zip", "hours", "services", "email", "privacy_policy_text"]
REASONS = ["New patient inquiry", "Appointment question", "Billing or insurance question", "Something else"]
SCHEMA_TYPES = {"dentist": "Dentist", "physician": "Physician", "medical": "MedicalBusiness", "therapy": "MedicalBusiness", "default": "MedicalBusiness"}
PLACEHOLDER = re.compile(r"\[[^\]]{2,}\]|\{\{[^}]+\}\}|lorem ipsum", re.I)


def _e(x):
    return html.escape(str(x), quote=True)


def _readable(hexcolor):
    h = hexcolor.lstrip("#")
    if len(h) != 6:
        h = "0b5cad"
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return "#ffffff" if lum < 0.4 else "#111111"


def check_intake(d, pages=1):
    """-> list of problems that stop the build (missing materials the client must supply)."""
    bad = [f"missing: {k}" for k in REQUIRED if not d.get(k)]
    if d.get("services") and len(d["services"]) > 8:
        bad.append("services: list at most 8")
    for k in ("practice_name", "privacy_policy_text", "address"):
        if PLACEHOLDER.search(str(d.get(k, ""))):
            bad.append(f"{k} still contains a placeholder")
    for ph in d.get("photos", []):
        if not ph.get("alt"):
            bad.append(f"photo {ph.get('file', '?')}: alt text is required")
    if pages == 3 and not d.get("about"):
        bad.append("missing: about (3-page site needs an about text)")
    return bad


def _css(brand):
    ink = _readable(brand)
    return f"""
:root{{--ink:#17202a;--muted:#4b5864;--bg:#fff;--soft:#f3f6f8;--line:#d9e0e6;--brand:{brand};--brand-ink:{ink}}}
@media (prefers-color-scheme:dark){{:root{{--ink:#e8edf2;--muted:#a9b6c2;--bg:#10161c;--soft:#18212a;--line:#2b3946}}}}
*{{box-sizing:border-box}}body{{margin:0;font:17px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}}
header,main,footer{{max-width:920px;margin:0 auto;padding:0 16px}}header{{display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;align-items:center;padding-top:16px;padding-bottom:16px}}
.brand{{font-weight:700;font-size:20px;text-decoration:none;color:var(--ink)}}nav a{{margin-right:14px;color:var(--ink)}}.call{{background:var(--brand);color:var(--brand-ink);padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:600}}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{{outline:3px solid var(--ink);outline-offset:2px}}
h1{{font-size:clamp(28px,5vw,40px);line-height:1.15;margin:28px 0 8px}}h2{{font-size:24px;margin:0 0 10px}}section{{padding:28px 0;border-top:1px solid var(--line)}}
.hero{{padding:24px 0 32px;border-top:0}}.lead{{font-size:19px;color:var(--muted);max-width:60ch}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
.card{{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:16px}}table{{border-collapse:collapse}}td{{padding:4px 18px 4px 0;vertical-align:top}}
form{{display:grid;gap:12px;max-width:520px}}label{{font-weight:600;display:grid;gap:4px}}input,select,textarea{{font:inherit;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}}
button{{font:inherit;background:var(--brand);color:var(--brand-ink);border:0;padding:12px 18px;border-radius:8px;font-weight:600;cursor:pointer}}.note{{font-size:14px;color:var(--muted)}}
.sample{{background:#fff4d6;color:#111;text-align:center;padding:8px;font-size:14px}}footer{{border-top:1px solid var(--line);padding-top:20px;padding-bottom:28px}}img{{max-width:100%;height:auto;border-radius:10px}}
"""


def _jsonld(d):
    t = SCHEMA_TYPES.get(d.get("business_type", "default"), SCHEMA_TYPES["default"])
    data = {"@context": "https://schema.org", "@type": t, "name": d["practice_name"], "telephone": d["phone"], "email": d["email"],
            "address": {"@type": "PostalAddress", "streetAddress": d["address"], "addressLocality": d["city"], "addressRegion": d["state"], "postalCode": d["zip"]}}
    if d.get("website"):
        data["url"] = d["website"]
    return json.dumps(data, indent=1).replace("</", "<\\/")


def _head(d, title, desc, css_inline=None):
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{_e(title)}</title>\n<meta name=\"description\" content=\"{_e(desc)}\">\n"
            f"<style>{css_inline}</style>\n<script type=\"application/ld+json\">{_jsonld(d)}</script></head><body>\n")


def _hours(d):
    return "<table>" + "".join(f"<tr><td>{_e(h['days'])}</td><td>{_e(h['hours'])}</td></tr>" for h in d["hours"]) + "</table>"


def _form(d):
    action = d.get("form_action")
    opts = "".join(f"<option>{_e(r)}</option>" for r in REASONS)
    target = f' action="{_e(action)}" method="post"' if action else f' action="mailto:{_e(d["email"])}" method="post" enctype="text/plain"'
    return (f'<form{target}><p class="note"><b>Please do not send health information</b> through this form. To discuss care, call {_e(d["phone"])}. In an emergency, call 911.</p>'
            '<label>Your name<input name="name" autocomplete="name" required></label>'
            '<label>Phone<input name="phone" type="tel" autocomplete="tel" required></label>'
            '<label>Email<input name="email" type="email" autocomplete="email"></label>'
            f'<label>What is this about?<select name="reason">{opts}</select></label>'
            '<button type="submit">Send</button></form>')


def _services(d):
    return '<div class="grid">' + "".join(f'<div class="card"><h3>{_e(s)}</h3></div>' for s in d["services"]) + "</div>"


def _doctors(d):
    if not d.get("doctors"):
        return ""
    return '<div class="grid">' + "".join(f'<div class="card"><h3>{_e(x["name"])}{", " + _e(x["credentials"]) if x.get("credentials") else ""}</h3>'
                                          f'<p>{_e(x.get("bio", ""))}</p></div>' for x in d["doctors"]) + "</div>"


def _photos(d, out):
    html_out = ""
    for ph in d.get("photos", [])[:3]:
        if os.path.exists(ph["file"]):
            os.makedirs(os.path.join(out, "images"), exist_ok=True)
            shutil.copy(ph["file"], os.path.join(out, "images", os.path.basename(ph["file"])))
            html_out += f'<img src="images/{_e(os.path.basename(ph["file"]))}" alt="{_e(ph["alt"])}" loading="lazy">'
    return html_out


def _policy_html(d):
    return "".join(f"<p>{_e(p.strip())}</p>" for p in re.split(r"\n\s*\n", d["privacy_policy_text"]) if p.strip())


def _chrome(d, nav, active_prefix=""):
    sample = '<div class="sample">Sample site for a fictional practice. Not a real business.</div>' if d.get("sample") else ""
    links = "".join(f'<a href="{href}">{_e(label)}</a>' for href, label in nav)
    return sample, (f'<header><a class="brand" href="{active_prefix}index.html">{_e(d["practice_name"])}</a>'
                    f'<nav aria-label="Main">{links}</nav><a class="call" href="tel:{_e(re.sub(r"[^0-9+]", "", d["phone"]))}">Call {_e(d["phone"])}</a></header>')


def _footer(d, privacy_href):
    return (f'<footer><p>{_e(d["practice_name"])} · {_e(d["address"])}, {_e(d["city"])}, {_e(d["state"])} {_e(d["zip"])} · {_e(d["phone"])}</p>'
            f'<p class="note"><a href="{privacy_href}">Privacy policy</a></p></footer></body></html>\n')


def build(intake, out, pages=1):
    """Writes the site into `out`. Raises ValueError listing what the client still has to supply."""
    d = dict(intake)
    d["brand_color"] = d.get("brand_color") or "#0b5cad"
    problems = check_intake(d, pages)
    if problems:
        raise ValueError("Intake incomplete:\n  - " + "\n  - ".join(problems))
    os.makedirs(out, exist_ok=True)
    css = _css(d["brand_color"])
    name = d["practice_name"]
    where = f'{d["city"]}, {d["state"]}'
    tagline = d.get("tagline") or f"Caring for patients in {where}"
    written = []
    ins = f'<p><b>Insurance accepted:</b> {_e(", ".join(d["insurance"]))}</p>' if d.get("insurance") else ""
    langs = f'<p><b>Languages:</b> {_e(", ".join(d["languages"]))}</p>' if d.get("languages") else ""
    booking = (f'<p><a class="call" href="{_e(d["booking_url"])}">Request an appointment online</a></p>' if d.get("booking_url") else "")
    gbp = f'<p><a href="{_e(d["google_business_url"])}">Find us on Google Maps</a></p>' if d.get("google_business_url") else ""
    contact_block = (f'<p>{_e(d["address"])}<br>{_e(where)} {_e(d["zip"])}<br><a href="tel:{_e(re.sub(r"[^0-9+]", "", d["phone"]))}">{_e(d["phone"])}</a><br>'
                     f'<a href="mailto:{_e(d["email"])}">{_e(d["email"])}</a></p>{ins}{langs}{gbp}')
    if pages == 1:
        sample, header = _chrome(d, [("#services", "Services"), ("#hours", "Hours"), ("#contact", "Contact")])
        body = (f'{sample}{header}<main><section class="hero"><h1>{_e(name)}</h1><p class="lead">{_e(tagline)}</p>{booking}{_photos(d, out)}</section>'
                f'<section id="services"><h2>Services</h2>{_services(d)}</section>'
                f'{"<section><h2>Our team</h2>" + _doctors(d) + "</section>" if d.get("doctors") else ""}'
                f'<section id="hours"><h2>Hours</h2>{_hours(d)}</section>'
                f'<section id="contact"><h2>Contact us</h2>{contact_block}{_form(d)}</section>'
                f'<section id="privacy"><h2>Privacy policy</h2>{_policy_html(d)}</section></main>')
        page = _head(d, f"{name} | {where}", f"{name} in {where}: services, hours, address and how to reach us.", css) + body + _footer(d, "#privacy")
        _w(out, "index.html", page)
        written.append("index.html")
    else:
        nav = [("index.html", "Home"), ("services.html", "Services"), ("about-contact.html", "About and contact")]
        for fname, title, inner in (
            ("index.html", f"{name} | {where}", f'<section class="hero"><h1>{_e(name)}</h1><p class="lead">{_e(tagline)}</p>{booking}{_photos(d, out)}</section>'
                                              f'<section><h2>Visit us</h2>{contact_block}</section><section><h2>Hours</h2>{_hours(d)}</section>'),
            ("services.html", f"Services | {name}", f'<section class="hero"><h1>Services</h1></section><section>{_services(d)}</section>'),
            ("about-contact.html", f"About and contact | {name}", f'<section class="hero"><h1>About us</h1><p>{_e(d["about"])}</p>{_doctors(d)}</section>'
                                                                  f'<section id="contact"><h2>Contact us</h2>{contact_block}{_form(d)}</section>'),
        ):
            sample, header = _chrome(d, nav)
            _w(out, fname, _head(d, title, f"{name} in {where}.", css) + sample + header + f"<main>{inner}</main>" + _footer(d, "privacy.html"))
            written.append(fname)
        sample, header = _chrome(d, nav)
        _w(out, "privacy.html", _head(d, f"Privacy policy | {name}", f"Privacy policy of {name}.", css) + sample + header
           + f'<main><section class="hero"><h1>Privacy policy</h1>{_policy_html(d)}</section></main>' + _footer(d, "privacy.html"))
        written.append("privacy.html")
    return written


def _w(out, fname, text):
    with open(os.path.join(out, fname), "w", encoding="utf-8") as fh:
        fh.write(text)


def qa(site_dir, intake=None):
    """The delivery checklist, automated. -> (problems, notes). Does not replace looking at it on a phone."""
    bad, notes = [], []
    pages = [f for f in sorted(os.listdir(site_dir)) if f.endswith(".html")]
    if not pages:
        return ["no .html files found"], []
    for f in pages:
        text = open(os.path.join(site_dir, f), encoding="utf-8").read()
        low = text.lower()
        if not re.search(r"<title>[^<]{5,}</title>", text):
            bad.append(f"{f}: missing or empty <title>")
        if 'name="description"' not in text:
            bad.append(f"{f}: missing meta description")
        if 'name="viewport"' not in text:
            bad.append(f"{f}: no viewport meta (not mobile friendly)")
        if PLACEHOLDER.search(re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)):
            bad.append(f"{f}: placeholder text left on the page")
        for m in re.finditer(r"<img\b[^>]*>", text):
            if "alt=" not in m.group(0):
                bad.append(f"{f}: image without alt text")
        if re.search(r'<(script|link|img|iframe)[^>]+(src|href)="https?://', text) and re.search(r'<(script|iframe|img)[^>]+src="https?://', text):
            bad.append(f"{f}: loads an external resource (speed and privacy)")
        if re.search(r'<link[^>]+rel="stylesheet"[^>]+href="https?://', text):
            bad.append(f"{f}: loads an external stylesheet")
        for m in re.finditer(r'<(input|textarea|select)\b[^>]*name="([^"]+)"', text):
            if re.search(r"symptom|diagnos|medic|condition|insurance|dob|birth|ssn|health|prescription", m.group(2), re.I):
                bad.append(f"{f}: form field {m.group(2)!r} could collect health information")
        if "<form" in low and "do not send health information" not in low:
            bad.append(f"{f}: form lacks the health-information warning")
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
            try:
                json.loads(m.group(1).replace("<\\/", "</"))
            except ValueError:
                bad.append(f"{f}: structured data is not valid JSON")
        size = len(text.encode("utf-8"))
        if size > 200_000:
            bad.append(f"{f}: {size // 1000} KB is heavy for a one-page site")
    if intake:
        everything = " ".join(open(os.path.join(site_dir, f), encoding="utf-8").read() for f in pages)
        flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", everything)))
        for key in ("phone", "address", "zip", "email"):
            if intake.get(key) and str(intake[key]) not in flat:
                bad.append(f"{key} from the intake does not appear on the site")
        for h in intake.get("hours", []):
            if h["hours"] not in flat:
                bad.append(f"hours {h['hours']!r} from the intake do not appear on the site")
    if any('action="mailto:' in open(os.path.join(site_dir, f), encoding="utf-8").read() for f in pages):
        notes.append("The form uses a mailto fallback, which is unreliable. Set form_action in the intake to a form service, and check that its data handling matches the privacy policy.")
    notes.append("Still check by hand: mobile and desktop, Chrome and Safari, form delivery to the right inbox, mobile speed test (target 80+), domain and SSL.")
    return bad, notes


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="leadengine site", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("intake", help="intake JSON (see examples/sample-practice/intake.json)")
    b.add_argument("--out", required=True)
    b.add_argument("--pages", type=int, choices=[1, 3], default=1)
    q = sub.add_parser("qa")
    q.add_argument("site_dir")
    q.add_argument("--intake", help="intake JSON, to check that phone, address, email and hours appear")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        with open(a.intake, encoding="utf-8") as fh:
            intake = json.load(fh)
        try:
            files = build(intake, a.out, a.pages)
        except ValueError as exc:
            print(exc)
            return 1
        print(f"Built {a.pages}-page site in {a.out}: {', '.join(files)}")
        problems, notes = qa(a.out, intake)
    else:
        intake = json.load(open(a.intake, encoding="utf-8")) if a.intake else None
        problems, notes = qa(a.site_dir, intake)
    for x in problems:
        print("  problem:", x)
    for x in notes:
        print("  note:", x)
    return 1 if problems else 0
