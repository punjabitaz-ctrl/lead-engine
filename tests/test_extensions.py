"""Contact discovery, company lists, pack-level rules, Places presence signals and the engagement feedback loop."""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import tempfile
import unittest
import urllib.error

from leadengine import batch, campaign, config, contacts, events, geo, packs, scoring, sources
from leadengine.engine import Engine

TODAY = dt.date(2026, 10, 27)
START = dt.date(2026, 10, 12)          # a Monday


def write(path, rows, fields):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


HOME = """<html><head><script>var x = "tracking@sentry.io";</script></head><body>
<a href="/about-us">About</a> <a href="/contact">Get in touch</a> <a href="https://other.test/contact">Partner</a>
<a href="/blog/post">Blog</a> <a href="/img/team.png">Team photo</a>
<a href="mailto:Info@Acme-Robotics.test?subject=Hi">Email us</a> <a href="tel:+1-732-555-0199">Call</a>
<a href="https://www.linkedin.com/company/acme-robotics/?trk=x">LinkedIn</a>
<p>Press: press [at] acme-robotics [dot] test. Logo: logo@2x.png. Write to noreply@acme-robotics.test.</p>
</body></html>"""
CONTACT = """<html><body><p>Partnerships: Dana Ruiz, dana.ruiz@acme-robotics.test</p><p>Our agency: help@gmail.com</p></body></html>"""


class ContactExtractTests(unittest.TestCase):
    def test_extract_finds_published_contacts_only(self):
        got = contacts.extract(HOME, "https://www.acme-robotics.test/")
        self.assertEqual(set(got["emails"]), {"info@acme-robotics.test", "press@acme-robotics.test"})
        self.assertEqual(got["phones"], ["7325550199"])
        self.assertEqual(got["linkedin"], ["https://www.linkedin.com/company/acme-robotics"])
        self.assertEqual(got["pages"], ["https://www.acme-robotics.test/about-us", "https://www.acme-robotics.test/contact"])

    def test_html_entities_and_scripts(self):
        got = contacts.extract("<p>sales&#64;acme.test</p><script>a='x@y.io'</script>", "https://acme.test")
        self.assertEqual(got["emails"], ["sales@acme.test"])

    def test_rank_prefers_own_domain_then_people_then_role_order(self):
        ranked = contacts.rank_emails(["help@gmail.com", "info@acme.test", "dana.ruiz@acme.test", "office@acme.test", "x@vendor.test"], "acme.test")
        self.assertEqual(ranked[:3], ["dana.ruiz@acme.test", "office@acme.test", "info@acme.test"])
        self.assertEqual(ranked[3], "help@gmail.com")
        self.assertEqual(contacts.rank_emails(["info@acme.test", "jlee@acme.test"], "acme.test", "Jo", "Lee")[0], "jlee@acme.test")

    def test_robots(self):
        txt = "User-agent: *\nDisallow: /contact\n"
        self.assertFalse(contacts.robots_allows(txt, "https://acme.test/contact"))
        self.assertTrue(contacts.robots_allows(txt, "https://acme.test/about"))
        self.assertTrue(contacts.robots_allows("", "https://acme.test/contact"))

    def test_domain_of(self):
        self.assertEqual(contacts.domain_of("http://WWW.Acme.test/x"), "acme.test")
        self.assertEqual(contacts.domain_of("acme.test"), "acme.test")


class FakeSite:
    def __init__(self, pages, robots="", robots_error=None):
        self.pages, self.robots, self.robots_error, self.calls = pages, robots, robots_error, []

    def __call__(self, url, timeout=12):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            if self.robots_error:
                raise self.robots_error
            return url, self.robots
        path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
        if path not in self.pages:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return url, self.pages[path]


class ContactFinderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def finder(self, site, **kw):
        return contacts.ContactFinder(self.dir, fetcher=site, sleep=lambda s: None, **kw)

    def test_finds_best_address_across_pages_and_caches(self):
        site = FakeSite({"/": HOME, "/contact": CONTACT, "/about-us": "<p>About</p>"})
        got = self.finder(site).find("https://www.acme-robotics.test/")
        self.assertEqual((got["email"], got["estatus"], got["phone"]), ("dana.ruiz@acme-robotics.test", "Risky", "7325550199"))
        self.assertEqual(got["linkedin"], "https://www.linkedin.com/company/acme-robotics")
        self.assertNotIn("https://other.test/contact", site.calls)
        again = FakeSite({})
        self.assertEqual(self.finder(again).find("acme-robotics.test")["email"], "dana.ruiz@acme-robotics.test")
        self.assertEqual(again.calls, [])

    def test_robots_disallow_is_respected(self):
        site = FakeSite({"/": "<a href='/contact'>Contact</a>", "/contact": CONTACT}, robots="User-agent: *\nDisallow: /contact")
        got = self.finder(site).find("https://acme-robotics.test")
        self.assertEqual(got["email"], "")
        self.assertNotIn("https://acme-robotics.test/contact", site.calls)

    def test_forbidden_robots_means_no_crawl_and_unreachable_is_skipped(self):
        site = FakeSite({"/": CONTACT}, robots_error=urllib.error.HTTPError("u", 403, "no", {}, None))
        self.assertEqual(self.finder(site).find("https://a.test")["email"], "")
        down = FakeSite({}, robots_error=OSError("dns"))
        self.assertIn("unreachable", self.finder(down).find("https://b.test")["note"])

    def test_off_domain_address_stays_unverified_and_cap_applies(self):
        f = self.finder(FakeSite({"/": "<p>help@gmail.com</p>"}), max_sites=1)
        self.assertEqual((f.find("https://c.test")["estatus"]), "Unverified")
        self.assertEqual(f.find("https://d.test")["email"], "")
        self.assertIn("cap", f.stopped)


def company_rows():
    return [
        {"company": "Acme Robotics GmbH", "website": "https://acme-robotics.test", "city": "Munich", "country": "Germany", "industry": "Robotics",
         "employees": "51-200", "signal": "Hiring: Head of US Channel Sales", "signal_date": "2026-10-20", "evidence": "LinkedIn post, Oct 20",
         "source": "my research"},
        {"company": "Nordlys XR AS", "website": "", "city": "Oslo", "country": "Norway", "industry": "XR", "employees": "20",
         "signal": "Exhibiting at CES 2027", "signal_date": "2026-10-15"},
        {"company": "Old News Ltd", "city": "Leeds", "country": "UK", "signal": "Opened a US office", "signal_date": "2025-01-01"},
        {"company": "Peak Staffing Partners LLC", "city": "Austin", "state": "TX"},
        {"company": "", "city": "Nowhere"},
    ]


class CompanyListTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.csv = os.path.join(self._tmp.name, "companies.csv")
        write(self.csv, company_rows(), sources.COMPANY_COLUMNS)

    def tearDown(self):
        self._tmp.cleanup()

    def test_source_reads_signals_and_dates(self):
        batch_ = next(sources.company_list(self.csv))
        self.assertEqual(len(batch_), 4)
        self.assertEqual(batch_[0]["signal_date"], dt.date(2026, 10, 20))
        self.assertEqual(batch_[0]["city_label"], "Munich, Germany")

    def test_missing_company_column_is_refused(self):
        bad = os.path.join(self._tmp.name, "bad.csv")
        write(bad, [{"name": "x"}], ["name"])
        with self.assertRaises(SystemExit):
            next(sources.company_list(bad))

    def test_engine_scores_hiring_and_expansion_and_applies_pack_rules(self):
        pack = {"id": "t", "tier_order": ["focus"], "tiers": {"focus": {}}, "ownership_exclude": [r"\bstaffing\b"],
                "config": {"size": {"basis": "employees", "small_max": 50, "medium_max": 500}}}
        cfg = config.load(None, pack)
        eng = Engine({"industry": "", "professions": [], "signal": "any"}, cfg, sources.company_list(self.csv), today=TODAY, pack=pack)
        eng.fill(10)
        leads = {ld["company"]: ld for ld in eng.take(10)}
        self.assertNotIn("Peak Staffing Partners LLC", leads)
        self.assertEqual(eng.stats["not_private"], 1)
        acme, nord, old = leads["Acme Robotics GmbH"], leads["Nordlys XR AS"], leads["Old News Ltd"]
        self.assertEqual((acme["hiring"], acme["strength"], acme["signal"], acme["source"]), ("Y", "hot", "Hiring", "List: my research"))
        self.assertEqual((nord["expand"], nord["strength"], nord["signal"]), ("Y", "hot", "Expansion"))
        self.assertEqual(old["strength"], "cold")
        self.assertEqual((acme["size_class"], nord["size_class"]), ("Medium", "Small"))
        self.assertIn("Source: my research", acme["notes"])
        self.assertIn("Evidence: LinkedIn post, Oct 20", acme["notes"])
        self.assertEqual(acme["detail"], "Head of US Channel Sales")
        self.assertIn("is hiring for Head of US Channel Sales", acme["body"])
        self.assertIn("Exhibiting at CES 2027", nord["body"])
        self.assertEqual(nord["country"], "Norway")

    def test_engine_fills_contacts_from_the_website(self):
        site = FakeSite({"/": HOME, "/contact": CONTACT})
        finder = contacts.ContactFinder(self._tmp.name, fetcher=site, sleep=lambda s: None)
        eng = Engine({"industry": "", "professions": [], "signal": "any"}, config.load(), sources.company_list(self.csv), today=TODAY,
                     contact_finder=finder)
        eng.fill(10)
        acme = next(ld for ld in eng.take(10) if ld["company"].startswith("Acme"))
        self.assertEqual((acme["email"], acme["estatus"], acme["phone"]), ("dana.ruiz@acme-robotics.test", "Risky", "7325550199"))
        self.assertIn("Contact found on:", acme["notes"])
        self.assertEqual(scoring.score(acme, config.load(), (), TODAY)["reach"], 5 + 5 + 5)


class PackRuleTests(unittest.TestCase):
    def test_role_rules_and_templates_come_from_the_pack(self):
        pack = packs.load("us-market-entry")
        self.assertTrue(packs.role_rules(pack))
        posting = [{"kind": "posting", "company": "Acme Robotics GmbH", "title": "Channel Sales Director, North America", "location": "Remote",
                    "posted": dt.date(2026, 10, 20), "job_type": "", "comp": None, "url": "", "metro": "Remote", "city_label": "Remote, US"},
                   {"kind": "posting", "company": "Acme Robotics GmbH", "title": "Web Developer", "location": "Remote",
                    "posted": dt.date(2026, 10, 20), "job_type": "", "comp": None, "url": "", "metro": "Remote", "city_label": "Remote, US"}]
        eng = Engine({"industry": pack["industry"], "professions": [], "signal": "any"}, config.load(None, pack), [posting], today=TODAY, pack=pack)
        eng.fill(5)
        leads = eng.take(5)
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["titles"], ["Channel Sales Director, North America"])
        self.assertNotIn("patients", leads[0]["body"])
        self.assertNotIn("Historical Philly", leads[0]["body"])
        self.assertIn("no thanks", leads[0]["body"])

    def test_every_pack_loads_and_names_real_templates(self):
        for pid in packs.available():
            pack = packs.load(pid)
            packs.templates(pack)                                       # raises if the file is missing
            for pat in packs.ownership_patterns(pack):
                self.assertTrue(pat.pattern)

    def test_default_size_basis_is_clinicians(self):
        cfg = config.load()
        self.assertEqual(scoring.size_class({"providers": 3, "emp": 900}, cfg), "Small")
        cfg["size"]["basis"] = "employees"
        self.assertEqual(scoring.size_class({"providers": 3, "emp": 900}, cfg), "Large")


class PlacesPresenceTests(unittest.TestCase):
    def test_listing_without_website_is_a_presence_gap(self):
        biz = [[{"kind": "business", "company": "Summit Roofing", "address": "", "website": "", "phone": "908-555-0100", "rating": 4.1,
                 "reviews": 3, "metro": "Summit", "city_label": "Summit, NJ"},
                {"kind": "business", "company": "Westfield Gutters", "address": "", "website": "https://wg.test", "phone": "", "rating": 4.8,
                 "reviews": 120, "metro": "Westfield", "city_label": "Westfield, NJ"}]]
        eng = Engine({"industry": "Roofing", "professions": [], "signal": "any"}, config.load(), biz, today=TODAY)
        eng.fill(5)
        leads = {ld["company"]: ld for ld in eng.take(5)}
        roof, gut = leads["Summit Roofing"], leads["Westfield Gutters"]
        self.assertEqual((roof["hasweb"], roof["hasgbp"], roof["reviews"], roof["signal"], roof["strength"]), ("N", "Y", 3, "No Presence", "warm"))
        self.assertEqual((gut["hasweb"], gut["strength"], gut["signal"]), ("Y", "cold", "General"))


class EventsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        campaign.init("ev", "NJ", counties=["Middlesex"], root=self.root)
        self.d = campaign.folder("ev", self.root)
        with open(os.path.join(self.d, "config.json")) as fh:
            cfg = json.load(fh)
        cfg["sender"].update(name="Sam Example", business="Example Studio", address="1 Main St, Edison, NJ 08817", offer="We help.")
        with open(os.path.join(self.d, "config.json"), "w") as fh:
            json.dump(cfg, fh)
        fields = ["Company", "Website", "City", "Email", "Email Status", "Phone", "LinkedIn URL", "Source", "Primary Signal",
                  "Draft Subject", "Draft Email 1", "Lead Key", "Decision"]
        rows = []
        for i, (src, sig) in enumerate((("NPPES", "No Presence"), ("NPPES", "Weak Site"), ("Google Maps", "No Presence"))):
            r = dict.fromkeys(fields, "")
            r.update(Company=f"Practice {i}", Website=f"practice{i}.test", City="Edison", Email=f"doc{i}@practice{i}.test", Source=src,
                     **{"Primary Signal": sig, "Draft Subject": "Hi", "Draft Email 1": "Hi.\nReply \"no thanks\" to stop.", "Decision": "Keep"})
            r["Lead Key"] = campaign.lead_key(r)
            rows.append(r)
        self.rows = rows
        write(os.path.join(self.d, "review", "pack-01.csv"), rows, fields)
        campaign.approve("ev", os.path.join(self.d, "review", "pack-01.csv"), self.root)
        self.tasks, _, _, _, _ = campaign.plan_outreach("ev", START, self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def events_file(self, rows):
        path = os.path.join(self.root, "events-in.csv")
        write(path, rows, ["Date", "Lead Key", "Company", "Email", "Event", "Notes"])
        return path

    def test_canonical_names(self):
        self.assertEqual(events.canonical("reply"), "Replied")
        self.assertEqual(events.canonical("Replied", "No thanks, we're all set"), events.OPT_OUT)
        self.assertEqual(events.canonical("Call booked"), "Call booked")
        self.assertIsNone(events.canonical("teleported"))

    def test_reply_stops_sequence_and_opt_out_is_suppressed(self):
        path = self.events_file([
            {"Date": "2026-10-13", "Email": "doc0@practice0.test", "Event": "reply", "Notes": "Sounds interesting, call me"},
            {"Date": "10/14/2026", "Lead Key": self.rows[1]["Lead Key"], "Event": "Replied", "Notes": "Please remove me from your list"},
            {"Date": "2026-10-14", "Company": "Practice 2", "Event": "bounce"},
            {"Date": "2026-10-14", "Company": "Stranger Co", "Event": "reply"},
            {"Date": "someday", "Company": "Practice 2", "Event": "reply"},
        ])
        res = events.import_events("ev", path, self.root, today=TODAY)
        self.assertEqual(res["imported"], 4)
        self.assertEqual(res["by_event"], {"Replied": 2, events.OPT_OUT: 1, "Bounced": 1})
        self.assertIn("doc1@practice1.test", res["suppressed_added"])
        self.assertIn("doc2@practice2.test", res["suppressed_added"])
        self.assertTrue(any("Stranger Co" in x for x in res["unmatched"]))
        self.assertEqual(len(res["skipped"]), 1)
        tasks, _ = campaign._read_csv(self.tasks)
        for t in tasks:
            if t["Company"] == "Practice 0":
                self.assertEqual(t["Done (Y/N)"], "Stopped" if t["Date"] >= "2026-10-13" else "", t)
        self.assertTrue(all(t["Done (Y/N)"] == "Stopped" for t in tasks if t["Company"] == "Practice 1" and t["Date"] >= "2026-10-14"))
        again = events.import_events("ev", path, self.root, today=TODAY)
        self.assertEqual((again["imported"], again["suppressed_added"], again["tasks_stopped"]), (0, [], 0))
        sup = campaign.load_suppressions("ev", self.root)
        self.assertTrue(campaign.suppressed(self.rows[1], sup))

    def test_stopped_drafts_leave_the_batch(self):
        day = next(t["Date"] for t in campaign._read_csv(self.tasks)[0] if t["Step"] == "1")
        before = batch.preview("ev", day, "email", self.root)["count"]
        events.import_events("ev", self.events_file([{"Date": "2026-10-01", "Email": "doc0@practice0.test", "Event": "opt out"}]), self.root, today=TODAY)
        self.assertEqual(batch.preview("ev", day, "email", self.root)["count"], before - 1)

    def test_interest_matches_the_sheet_rules(self):
        ev = lambda name, day="2026-10-20": {"Event": name, "Points": events.EVENTS[name], "Date": day}
        self.assertEqual(events.interest([], TODAY), "No contact yet")
        self.assertEqual(events.interest([ev("Email link clicked")], TODAY), "Cold")
        self.assertEqual(events.interest([ev("Replied")], TODAY), "Warm")
        self.assertEqual(events.interest([ev("Call booked")], TODAY), "Hot")
        self.assertEqual(events.interest([ev("Call booked", "2026-08-01")], TODAY), "Cold")
        self.assertEqual(events.interest([ev("Call booked"), ev(events.OPT_OUT)], TODAY), "Opted out")

    def test_report_rates_by_source_and_signal(self):
        tasks, fields = campaign._read_csv(self.tasks)
        for t in tasks:
            if t["Step"] == "1":
                t["Done (Y/N)"] = "Y"
        write(self.tasks, tasks, fields)
        events.import_events("ev", self.events_file([{"Date": "2026-10-20", "Email": "doc0@practice0.test", "Event": "Call booked"}]), self.root, today=TODAY)
        rep = events.report("ev", self.root, today=TODAY)
        self.assertEqual(rep["contacted"], 3)
        self.assertEqual(rep["hot_leads"], ["Practice 0"])
        self.assertEqual(rep["by_source"]["NPPES"]["booking_rate"], 0.5)
        self.assertEqual(rep["by_signal"]["No Presence"]["booked"], 1)
        self.assertIn("3 of 200", rep["tuning"])

    def test_cli(self):
        path = self.events_file([{"Date": "2026-10-13", "Email": "doc0@practice0.test", "Event": "reply"}])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            campaign.main(["--root", self.root, "events", "import", "ev", path])
            campaign.main(["--root", self.root, "events", "report", "ev"])
        self.assertIn("1 events logged", out.getvalue())
        self.assertIn('"contacted"', out.getvalue())


class CampaignCompaniesTests(unittest.TestCase):
    def test_run_discover_from_a_company_list_with_the_pack(self):
        with tempfile.TemporaryDirectory() as root:
            spec, problems = campaign.init("entry", "NJ", cities=["Newark, NJ"], vertical="us-market-entry", root=root)
            self.assertEqual(problems, [])
            self.assertIn("the companies source reads a file", " ".join(campaign.blockers(spec)))
            lst = os.path.join(root, "list.csv")
            write(lst, company_rows(), sources.COMPANY_COLUMNS)
            old = os.getcwd()
            os.chdir(root)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    out = campaign.run_discover("entry", root, target=10, companies=lst)
            finally:
                os.chdir(old)
            rows, _ = campaign._read_csv(out[0])
            self.assertEqual(rows[0]["Company"], "Acme Robotics GmbH")
            self.assertNotIn("Peak Staffing Partners LLC", {r["Company"] for r in rows})
            self.assertTrue(all("patients" not in r["Draft Email 1"] for r in rows))


if __name__ == "__main__":
    unittest.main()


PLACE_FILE = """STATE|STATEFP|COUNTYFP|COUNTYNAME|PLACEFP|PLACENS|PLACENAME|TYPE|CLASSFP|FUNCSTAT
TX|48|453|Travis County|05000|02409761|Austin city|INCORPORATED PLACE|C1|A
TX|48|453|Travis County|40864|02410863|Lakeway city|INCORPORATED PLACE|C1|A
TX|48|491|Williamson County|05000|02409761|Austin city|INCORPORATED PLACE|C1|A
TX|48|453|Travis County|99999|00000000|Ghost CDP|CENSUS DESIGNATED PLACE|U1|F
LA|22|071|Orleans Parish|55000|00545142|New Orleans city|INCORPORATED PLACE|C7|A
"""
COUSUB_FILE = """STATE|STATEFP|COUNTYFP|COUNTYNAME|COUSUBFP|COUSUBNS|COUSUBNAME|CLASSFP|FUNCSTAT
NJ|34|003|Bergen County|61980|00882226|Ridgewood village|T1|A
NJ|34|003|Bergen County|00000|00000000|County subdivisions not defined|Z9|F
NJ|34|023|Middlesex County|20230|00882164|Edison township|T1|A
NJ|34|023|Middlesex County|51210|00885318|New Brunswick city|C5|A
"""


class GeoBuildTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.places, self.cousubs = os.path.join(self.dir, "places.txt"), os.path.join(self.dir, "cousub.txt")
        with open(self.places, "w") as fh:
            fh.write(PLACE_FILE)
        with open(self.cousubs, "w") as fh:
            fh.write(COUSUB_FILE)

    def tearDown(self):
        self._tmp.cleanup()

    def test_parse_strips_legal_suffixes_and_skips_inactive(self):
        got = geo.parse_census(PLACE_FILE)
        self.assertEqual(got["TX"], {"Travis": ["Austin", "Lakeway"], "Williamson": ["Austin"]})
        self.assertEqual(got["LA"], {"Orleans": ["New Orleans"]})
        self.assertEqual(geo.parse_census(COUSUB_FILE)["NJ"]["Bergen"], ["Ridgewood"])
        self.assertEqual(geo.place_name("Boise City city"), "Boise City")
        with self.assertRaises(SystemExit):
            geo.parse_census("a,b,c\n1,2,3")

    def test_build_writes_states_and_keeps_hand_entered_names(self):
        out = os.path.join(self.dir, "geo")
        os.makedirs(out)
        with open(os.path.join(out, "NJ.json"), "w") as fh:
            json.dump({"state": "NJ", "counties": {"Middlesex": ["Edison", "Iselin"]}, "cities": ["Newark"]}, fh)
        done = geo.build([self.places, self.cousubs], out_dir=out)
        self.assertEqual(set(done), {"TX", "LA", "NJ"})
        with open(os.path.join(out, "NJ.json")) as fh:
            nj = json.load(fh)
        self.assertEqual(nj["counties"]["Middlesex"], ["Edison", "New Brunswick", "Iselin"])
        self.assertEqual(nj["cities"], ["Newark"])                       # a curated sweep list is kept
        with open(os.path.join(out, "TX.json")) as fh:
            tx = json.load(fh)
        self.assertEqual(tx["cities"], ["Austin", "Lakeway"])           # no list before: every place
        old = geo.GEO_DIR
        geo.GEO_DIR = out
        try:
            self.assertEqual(geo.county_cities(["Travis County"], "tx"), [("Austin", "TX"), ("Lakeway", "TX")])
            self.assertEqual(geo.resolve({"state": "LA", "counties": ["Orleans Parish"]}), [("New Orleans", "LA")])
        finally:
            geo.GEO_DIR = old

    def test_only_named_states_and_unreadable_source(self):
        out = os.path.join(self.dir, "geo2")
        self.assertEqual(set(geo.build([self.places], ["la"], out)), {"LA"})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(geo.main(["build", "--file", os.path.join(self.dir, "missing.txt"), "--out", out]), 1)
        self.assertIn("census.gov", err.getvalue())


class ZipAndCapTests(unittest.TestCase):
    def test_zip_codes_resolve_with_their_state(self):
        self.assertEqual(geo.resolve({"state": "nj", "zips": ["07960"], "cities": ["Summit, NJ"]}), [("Summit", "NJ"), ("07960", "NJ")])
        for bad in ({"state": "NJ", "zips": ["7960"]}, {"zips": ["07960"]}):
            with self.assertRaises(SystemExit):
                geo.resolve(bad)

    def test_spend_cap_counts_per_run_and_month(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "usage.json")
            cap = sources.SpendCap(path, run_cap=2, monthly_cap=3, today=TODAY)
            self.assertEqual([cap.take(), cap.take(), cap.take()], [True, True, False])
            self.assertIn("per-run", cap.stopped)
            cap2 = sources.SpendCap(path, run_cap=5, monthly_cap=3, today=TODAY)
            self.assertEqual([cap2.take(), cap2.take()], [True, False])
            self.assertIn("monthly", cap2.stopped)

    def test_places_sweep_stops_at_the_cap(self):
        calls = []

        def fake(url, data=None, headers=None):
            calls.append(json.loads(data)["textQuery"])
            return {"places": [{"displayName": {"text": f"Biz {len(calls)}"}}], "nextPageToken": "more"}

        old = os.environ.get("GOOGLE_PLACES_API_KEY")
        os.environ["GOOGLE_PLACES_API_KEY"] = "test-not-a-key"
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                got = list(sources.places_businesses([("Summit", "NJ"), ("Westfield", "NJ")], ["plumber", "electrician"],
                                                     cap=sources.SpendCap(None, run_cap=3), fetch=fake))
        finally:
            if old is None:
                del os.environ["GOOGLE_PLACES_API_KEY"]
            else:
                os.environ["GOOGLE_PLACES_API_KEY"] = old
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(got), 3)


class TradesPackTests(unittest.TestCase):
    def test_franchises_dropped_and_local_templates_used(self):
        pack = packs.load("local-services")
        self.assertEqual(packs.terms(pack, "places_queries"), ["plumber", "electrician"])
        biz = [[{"kind": "business", "company": name, "address": "", "website": web, "phone": "", "rating": 4.5, "reviews": rev,
                 "metro": "Summit", "city_label": "Summit, NJ"} for name, web, rev in
                (("Roto-Rooter Plumbing & Water Cleanup", "", 400), ("Mr. Rooter Plumbing of Union County", "", 90),
                 ("Summit Family Plumbing", "", 4), ("Bright Spark Electric LLC", "https://brightspark.test", 6))]]
        eng = Engine({"industry": pack["industry"], "professions": [], "signal": "any"}, config.load(None, pack), biz, today=TODAY, pack=pack)
        eng.fill(10)
        leads = {ld["company"]: ld for ld in eng.take(10)}
        self.assertEqual(set(leads), {"Summit Family Plumbing", "Bright Spark Electric LLC"})
        self.assertIn("couldn't find a website", leads["Summit Family Plumbing"]["body"])
        self.assertIn("before they call", leads["Bright Spark Electric LLC"]["body"])
        self.assertNotIn("patients", " ".join(ld["body"] for ld in leads.values()))

    def test_medical_chains_dropped_in_any_state(self):
        pack = packs.load("healthcare-practices")
        page = {"results": [
            {"number": "1", "enumeration_type": "NPI-2", "basic": {"organization_name": "ASPEN DENTAL MANAGEMENT INC", "status": "A"},
             "addresses": [{"address_purpose": "LOCATION", "city": "AUSTIN", "state": "TX"}], "taxonomies": [{"desc": "Dentist", "primary": True}]},
            {"number": "2", "enumeration_type": "NPI-2", "basic": {"organization_name": "LAKEWAY SMILES PLLC", "status": "A"},
             "addresses": [{"address_purpose": "LOCATION", "city": "LAKEWAY", "state": "TX"}], "taxonomies": [{"desc": "Dentist", "primary": True}]}]}
        eng = Engine({"industry": "", "professions": [], "signal": "any"}, config.load(None, pack),
                     [sources.parse_nppes(page, "Austin", "TX")], today=TODAY, pack=pack)
        eng.fill(5)
        self.assertEqual([ld["company"] for ld in eng.take(5)], ["LAKEWAY SMILES PLLC"])
