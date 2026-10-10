"""One-page landing page for a campaign, generated from its spec and sender config so prices, dates and limits can never drift from the offer.

`leadengine campaign landing <name>` writes campaigns/<name>/landing/index.html: a single self-contained file (inline CSS, no external requests)
that you upload to your own site. The tracker snippet is included only when sender.tracker_base is set."""
import datetime as dt
import html
import os
import re

from . import campaign

PLACEHOLDER = re.compile(r"\[[^\]]+\]")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _e(x):
    return html.escape(str(x), quote=True)


def _money(x):
    return f"${x:,.2f}".rstrip("0").rstrip(".") if isinstance(x, float) and x % 1 else f"${int(x):,}"


def _date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _tracker(cfg):
    base = (cfg["sender"].get("tracker_base") or "").rstrip("/")
    if not base:
        return "", ""
    with open(os.path.join(ROOT, "tracker", "track.js"), encoding="utf-8") as fh:
        js = fh.read()
    js = re.sub(r'var ENDPOINT = "[^"]*";', f'var ENDPOINT = {_e(base + "/e")!r};'.replace("'", '"'), js)
    js = re.sub(r"/\*.*?\*/", "", js, count=1, flags=re.S)
    return f"<script>{js}</script>", "<p class=\"small\">If you arrive from one of our emails, we record that you visited this page so we know the email reached you. We store no other personal information from your visit.</p>"


def render(spec, cfg):
    """-> (html, warnings)"""
    s, off = cfg["sender"], spec["offer"]
    lau = off["launch"]
    warnings = []
    biz = s.get("business", "")
    if PLACEHOLDER.search(biz) or not biz:
        warnings.append("sender.business is still a placeholder")
    cta = s.get("booking_link") or (f"mailto:{s['reply_email']}" if s.get("reply_email") else "")
    if not cta:
        warnings.append("set sender.booking_link or sender.reply_email so the page has a call to action")
        cta = "#contact"
    w = campaign.launch_window(spec)
    if not w:
        warnings.append("the launch window has not started (`campaign launch <name> --start DATE`); the page omits the dates")
    prod = {p["id"]: p for p in off["products"]}
    plans = off["plans"]
    addons = {a["id"]: a for a in off.get("add_ons", [])}
    p1, p3 = prod["page1"], prod["page3"]
    dep = p3["payment"].get("percent", 50)
    launch_line = ""
    if w:
        launch_line = (f"<div class=\"launch\"><strong>Launch pricing.</strong> The first {lau['max_customers']} clients who sign before "
                       f"{_e(_date(str(w[1])))} keep these prices for {lau['lock_months']} months from signing. This date is fixed.</div>")
    plan_cards = "".join(
        f"<div class=\"card\"><h3>{_e(p['name'])}</h3><p class=\"price\">{_money(p['price'])}<span>/month</span></p><p>{_e(p['includes'].capitalize())}.</p></div>" for p in plans)
    addon_rows = "".join(f"<li><span>{_e(a['name'])}</span><b>{_money(a['price'])}{'/' + a['unit'] if a.get('unit') else ''}</b></li>"
                         for a in addons.values() if a.get("price"))
    intake = "".join(f"<li>{_e(x[0].upper() + x[1:])}</li>" for x in off["intake_required"])
    track_js, track_note = _tracker(cfg)
    title = f"{biz}: a professional website for your practice, live in 72 hours"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<meta name="description" content="A clean, mobile-friendly website for your practice from {_money(p1['price'])}, live within 72 hours of payment and your materials. Fixed prices.">
<style>
:root{{--ink:#17202a;--muted:#4b5864;--bg:#fff;--soft:#f3f6f8;--line:#d9e0e6;--brand:#0b5cad;--brand-ink:#fff;--warn:#fff4d6}}
@media (prefers-color-scheme:dark){{:root{{--ink:#e8edf2;--muted:#a9b6c2;--bg:#10161c;--soft:#18212a;--line:#2b3946;--brand:#4da3ff;--brand-ink:#08121c;--warn:#2a2410}}}}
*{{box-sizing:border-box}}body{{margin:0;font:17px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}}
main{{max-width:880px;margin:0 auto;padding:0 16px 48px}}section{{padding:36px 0;border-top:1px solid var(--line)}}section:first-of-type{{border-top:0}}
h1{{font-size:clamp(28px,5vw,42px);line-height:1.15;margin:40px 0 12px}}h2{{font-size:24px;margin:0 0 12px}}h3{{font-size:18px;margin:0 0 6px}}
.lead{{font-size:19px;color:var(--muted);max-width:60ch}}.btn{{display:inline-block;background:var(--brand);color:var(--brand-ink);padding:13px 22px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:12px}}
.btn:focus-visible,a:focus-visible{{outline:3px solid var(--ink);outline-offset:2px}}.launch{{background:var(--warn);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:20px 0}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}.card{{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:18px}}
.price{{font-size:30px;font-weight:700;margin:4px 0}}.price span{{font-size:15px;font-weight:400;color:var(--muted)}}ul{{padding-left:20px}}.small{{font-size:14px;color:var(--muted)}}
ol.steps{{padding-left:22px}}ol.steps li{{margin-bottom:8px}}ul.rows{{list-style:none;padding:0}}ul.rows li{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:8px 0}}
details{{border-bottom:1px solid var(--line);padding:10px 0}}summary{{cursor:pointer;font-weight:600}}footer{{border-top:1px solid var(--line);padding:24px 16px;max-width:880px;margin:0 auto}}
</style></head><body><main>
<section><h1>A professional website for your practice, live in 72 hours.</h1>
<p class="lead">Fixed prices from {_money(p1['price'])}. You send your logo, photos and text once. We build it, launch it, and keep it online.</p>
{launch_line}<a class="btn" href="{_e(cta)}">Book a short call</a> <span class="small">or reply to our email</span></section>
<section><h2>Two sites, one price each</h2><div class="cards">
<div class="card"><h3>One-page site</h3><p class="price">{_money(p1['price'])}</p><p>Your practice name, services, location and map, hours, phone and a simple contact form. Mobile-friendly. Paid in full before work starts.</p></div>
<div class="card"><h3>Three-page site</h3><p class="price">{_money(p3['price'])}</p><p>Home, services, and about/contact, plus a basic privacy notice. {dep}% deposit before work starts, the balance when your site launches.</p></div></div>
<p class="small">The 72 hours begin when we have your payment and everything on the list below. Both sites include one round of revisions.</p></section>
<section><h2>Keep it online and up to date</h2><div class="cards">{plan_cards}</div>
<p class="small">Plans are month to month. Unused changes do not roll over. Work beyond a plan's limits is quoted separately before it starts.</p></section>
<section><h2>How it works</h2><ol class="steps">
<li><b>Talk for 15 minutes</b> or reply to our email with questions.</li>
<li><b>Sign and pay.</b> {_money(p1['price'])} in full for one page, or the {dep}% deposit ({_money(p3['price'] * dep / 100)}) for three pages.</li>
<li><b>Send your materials once</b> (the list below).</li>
<li><b>Your site is live within 72 hours</b> of payment and complete materials, with a preview along the way.</li></ol></section>
<section><h2>What we need from you before we start</h2><ul>{intake}</ul>
<p class="small">If you do not have a privacy policy or a logo, we can quote that separately. Work starts once they exist.</p></section>
{('<section><h2>Optional add-ons</h2><ul class="rows">' + addon_rows + '</ul></section>') if addon_rows else ''}
<section id="faq"><h2>Questions</h2>
<details><summary>Do the sites collect patient information?</summary><p>No. The contact form asks for a name, phone number and a general reason only, and tells visitors not to send health information. We do not handle protected health information or sign business associate agreements.</p></details>
<details><summary>Who owns the site?</summary><p>You do, once it is paid in full. Your domain stays in your name.</p></details>
<details><summary>What if I need more than my plan includes?</summary><p>We quote it in writing before any work starts, and you decide.</p></details>
<details><summary>How long do launch prices last?</summary><p>For the first {lau['max_customers']} clients who sign before the end date, for {lau['lock_months']} months from signing. After that, regular prices apply to new clients.</p></details>
<details><summary>Do you call me?</summary><p>No cold calls. We reach out by email and LinkedIn, and we call only if you ask us to.</p></details></section>
<section id="contact"><h2>Ready?</h2><a class="btn" href="{_e(cta)}">Book a short call</a>{'<p class="small">Or email ' + _e(s['reply_email']) + '</p>' if s.get('reply_email') else ''}</section>
</main><footer><p class="small">{_e(biz)}{' · ' + _e(s['address']) if s.get('address') and not PLACEHOLDER.search(s['address']) else ''} · All prices in US dollars.</p>{track_note}</footer>{track_js}</body></html>
"""
    left = PLACEHOLDER.findall(re.sub(r"<script>.*?</script>", "", page, flags=re.S))
    if left:
        warnings.append("placeholders left on the page: " + ", ".join(sorted(set(left))))
    if not off.get("add_ons"):
        warnings.append("no add-ons listed")
    return page, warnings


def write(name, root=campaign.ROOT):
    from . import config
    spec = campaign.load(name, root)
    cfg = config.load(os.path.join(campaign.folder(name, root), "config.json"))
    page, warnings = render(spec, cfg)
    out = os.path.join(campaign.folder(name, root), "landing", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    campaign.log(name, "landing", root, warnings=len(warnings))
    return out, warnings
