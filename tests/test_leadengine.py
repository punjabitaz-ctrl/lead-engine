import datetime as dt
import unittest

from leadengine import audit, config, scoring
from leadengine.filters import RoleRules, is_blocked, is_public_sector, load_blocklist, norm_name

TODAY = dt.date(2026, 10, 8)
CFG = config.load()


class FilterTests(unittest.TestCase):
    def test_blocklist_whole_word(self):
        bl = load_blocklist()
        self.assertTrue(is_blocked("Deloitte", bl))
        self.assertTrue(is_blocked("M/I Homes", bl))
        self.assertFalse(is_blocked("Advisal Group", bl))  # 'visa' must not match inside a word

    def test_public_sector(self):
        self.assertTrue(is_public_sector("Ohio Public Employees Retirement System"))
        self.assertFalse(is_public_sector("EarthCam Inc"))

    def test_role_rules(self):
        r = RoleRules(["web developer"])
        self.assertTrue(r.relevant("E-Commerce Manager"))
        self.assertTrue(r.relevant("Director of Marketing"))
        self.assertFalse(r.relevant("Frontend Developer - AI Trainer"))
        self.assertFalse(r.relevant("Manufacturing Engineer, Front-End Cell Assembly"))
        self.assertFalse(r.relevant("Customer Service Manager"))

    def test_norm_name(self):
        self.assertEqual(norm_name("EarthCam Inc."), "earthcam")
        self.assertEqual(norm_name("The Hershey Company"), "hershey")


class AuditTests(unittest.TestCase):
    def test_flags_old_unresponsive_site(self):
        html = "<html><body>Welcome &copy; 2019 Acme</body></html>"
        outdated, notes = audit.analyze_html(html, "http://acme.test", today=TODAY)
        self.assertTrue(outdated)
        self.assertEqual(len(notes), 3)

    def test_clean_site(self):
        html = '<meta name="viewport" content="width=device-width"><footer>© 2026 Acme</footer>'
        self.assertEqual(audit.analyze_html(html, "https://acme.test", today=TODAY), (False, []))


class ScoringTests(unittest.TestCase):
    def test_matches_sheet_example(self):
        # Same lead as the 'Delta Fintech' row used to verify the workbook: 30 + 40 + 20 + 10 = 100
        lead = {"vertical": "Fintech", "emp": 200, "city": "Atlanta", "hiring": "Y", "expand": "Y", "psi": 45,
                "outdated": "Y", "estatus": "Valid", "phone": "555", "linkedin": "x", "sigdate": TODAY - dt.timedelta(days=2)}
        s = scoring.score(lead, CFG, ["Fintech"], TODAY)
        self.assertEqual((s["fit"], s["urg"], s["reach"], s["fresh"], s["total"], s["grade"]), (30, 40, 20, 10, 100, "A"))

    def test_signal_strength(self):
        fresh = {"hiring": "Y", "sigdate": TODAY - dt.timedelta(days=5), "n_postings": 1}
        mid = {"hiring": "Y", "sigdate": TODAY - dt.timedelta(days=60), "n_postings": 1}
        old = {"hiring": "Y", "sigdate": TODAY - dt.timedelta(days=200), "n_postings": 1}
        self.assertEqual([scoring.strength(x, CFG, TODAY) for x in (fresh, mid, old)], ["hot", "warm", "cold"])


NPPES_PAGE = {"results": [
    {"number": "1111111111", "enumeration_type": "NPI-2",
     "basic": {"organization_name": "GARDEN STATE FAMILY CARE LLC", "status": "A", "authorized_official_first_name": "ANA",
               "authorized_official_last_name": "PEREZ", "authorized_official_title_or_position": "OWNER"},
     "addresses": [{"address_purpose": "MAILING", "city": "Trenton"},
                   {"address_purpose": "LOCATION", "address_1": "1 MAIN ST", "city": "NEWARK", "state": "NJ", "telephone_number": "973-555-0101"}],
     "taxonomies": [{"desc": "Family Medicine", "primary": True}]},
    {"number": "2222222222", "enumeration_type": "NPI-2",
     "basic": {"organization_name": "RWJBarnabas Health Medical Group", "status": "A"},
     "addresses": [{"address_purpose": "LOCATION", "city": "NEWARK", "state": "NJ", "telephone_number": "973-555-0102"}],
     "taxonomies": [{"desc": "Family Medicine", "primary": True}]},
    {"number": "3333333333", "enumeration_type": "NPI-1",
     "basic": {"first_name": "JOE", "last_name": "LEE", "credential": "M.D.", "sole_proprietor": "NO", "status": "A"},
     "addresses": [{"address_purpose": "LOCATION", "city": "NEWARK", "state": "NJ", "telephone_number": "973-555-0103"}],
     "taxonomies": [{"desc": "Pediatrics", "primary": True}]},
    {"number": "4444444444", "enumeration_type": "NPI-1",
     "basic": {"first_name": "SAM", "last_name": "OKAFOR", "credential": "D.O.", "sole_proprietor": "YES", "status": "A"},
     "addresses": [{"address_purpose": "LOCATION", "city": "NEWARK", "state": "NJ", "telephone_number": "973-555-0104"}],
     "taxonomies": [{"desc": "Internal Medicine", "primary": True}]},
]}


class ProviderTests(unittest.TestCase):
    def run_engine(self, presence_data=None, signal="any"):
        from leadengine import sources
        from leadengine.engine import Engine
        batch = sources.parse_nppes(NPPES_PAGE, "Newark", "NJ")
        return Engine({"signal": signal, "industry": "Medical practice", "professions": []}, CFG, [batch], today=TODAY,
                      presence_data=presence_data)

    def test_parse_uses_location_and_authorized_official(self):
        from leadengine import sources
        got = sources.parse_nppes(NPPES_PAGE, "Newark", "NJ")
        self.assertEqual(len(got), 4)
        self.assertEqual((got[0]["phone"], got[0]["first"], got[0]["title"], got[0]["city_label"]),
                         ("973-555-0101", "Ana", "OWNER", "Newark, NJ"))

    def test_private_filter(self):
        e = self.run_engine()
        e.fill(10)
        names = sorted(l["company"] for l in e.take(10))
        self.assertEqual(names, ["GARDEN STATE FAMILY CARE LLC", "Sam Okafor, D.O."])  # health system + non-sole NPI-1 dropped
        self.assertEqual(e.stats["not_private"], 2)

    def test_confirmed_gap_scores_and_ranks_first(self):
        e = self.run_engine({"1111111111": {"hasweb": "N", "hasgbp": "N", "reviews": None}}, signal="warm")
        e.fill(10)
        got = e.take(10)
        self.assertEqual([l["company"] for l in got], ["GARDEN STATE FAMILY CARE LLC"])  # unchecked leads are 'cold'
        lead = got[0]
        # fit: vertical not in query list? (industry given -> matches) 10 + metro 10; urgency 20+12; reach: phone 5
        self.assertEqual((lead["strength"], lead["signal"], lead["urg"], lead["reach"]), ("hot", "No Presence", 32, 5))
        self.assertIn("couldn't find a website", lead["body"])


class ThinProfileTests(unittest.TestCase):
    def test_thin_profile_signal_and_draft(self):
        from leadengine import drafts
        lead = {"company": "Bright Eye Care", "website": "https://brighteye.test", "city": "Edison", "reviews": 4, "hasweb": "Y",
                "hasgbp": "Y", "first": "Dr. Rao"}
        self.assertEqual(scoring.primary_signal(lead, CFG), "Thin Profile")
        self.assertEqual(scoring.strength(lead, CFG, TODAY), "warm")
        sig, subj, body = drafts.draft(lead, CFG)
        self.assertIn("only 4 Google reviews", body)
        self.assertIn("Google reviews", subj)
        lead["reviews"] = 250
        self.assertEqual(scoring.primary_signal(lead, CFG), "General")


class SizeTests(unittest.TestCase):
    def test_size_class(self):
        self.assertEqual([scoring.size_class({"providers": n}, CFG) for n in (1, 2, 5, 6, 15, 16)],
                         ["Solo", "Small", "Small", "Medium", "Medium", "Large"])
        self.assertEqual(scoring.size_class({}, CFG), "Unknown")
        self.assertEqual(scoring.size_class({"providers": 2, "sizeov": "Large"}, CFG), "Large")

    def test_exclude_large(self):
        import copy
        from leadengine import sources
        from leadengine.engine import Engine
        batch = [dict(kind="provider", company=n, npi="", npi_type="NPI-2", sole="", first="", last="", title="", specialty="x",
                      phone="", address="", loc_city="Edison", metro="Edison", city_label="Edison, NJ", priority=2, evidence="",
                      origin="Web search (unverified)", origin_note="", providers=p, size_override=o)
                 for n, p, o in (("Solo Heart", 1, ""), ("Chain Heart", None, "Large"), ("Big Heart", 40, ""))]
        cfg = copy.deepcopy(CFG)
        cfg["exclude_large"] = True
        e = Engine({"signal": "any", "industry": "Medical practice", "professions": []}, cfg, [batch], today=TODAY)
        e.fill(10)
        self.assertEqual([l["company"] for l in e.take(10)], ["Solo Heart"])


class CheckerTests(unittest.TestCase):
    def test_cache_and_caps(self):
        import tempfile
        from unittest import mock
        from leadengine import presence
        with tempfile.TemporaryDirectory() as d:
            calls = []

            def fake(name, city, state, phone=""):
                calls.append(name)
                return {"hasweb": "N", "hasgbp": "N", "reviews": None}

            with mock.patch.object(presence, "_places_lookup", fake):
                c = presence.PlacesChecker(d, run_cap=2, monthly_cap=10, today=TODAY)
                c.check("A Dental", "Newark", "NJ")
                c.check("A Dental", "Newark", "NJ")           # cached: no second call
                c.check("B Dental", "Newark", "NJ")
                self.assertIsNone(c.check("C Dental", "Newark", "NJ"))   # run cap hit
                self.assertEqual((calls, c.calls), (["A Dental", "B Dental"], 2))
                self.assertIn("per-run cap", c.stopped)
                c2 = presence.PlacesChecker(d, run_cap=5, monthly_cap=2, today=TODAY)   # new run, same month
                self.assertIsNotNone(c2.check("A Dental", "Newark", "NJ"))             # cache still free
                self.assertIsNone(c2.check("D Dental", "Newark", "NJ"))                # monthly cap (2 already used)
                self.assertIn("monthly cap", c2.stopped)

    def test_failed_lookup_is_not_a_confirmed_gap(self):
        import tempfile
        from unittest import mock
        from leadengine import presence
        with tempfile.TemporaryDirectory() as d, mock.patch.object(presence, "_places_lookup", lambda *a, **k: None):
            c = presence.PlacesChecker(d, today=TODAY)
            self.assertIsNone(c.check("X", "Newark", "NJ"))
            self.assertEqual((c.calls, c.cache), (0, {}))


class KeyTests(unittest.TestCase):
    def test_keys(self):
        from leadengine.keys import dedupe_key, tracked_link
        self.assertEqual(dedupe_key("https://www.EarthCam.net/about", "EarthCam Inc", "Newark"), "earthcam.net")
        self.assertEqual(dedupe_key("", " Garden State Family Care ", "Newark"), "garden state family care|newark")
        self.assertEqual(tracked_link("https://x.supabase.co/functions/v1/lead-tracker/", "a b|c", "https://tazabbas.com/projects", "redirect"),
                         "https://x.supabase.co/functions/v1/lead-tracker/t?l=a%20b%7Cc&to=https%3A%2F%2Ftazabbas.com%2Fprojects")
        self.assertEqual(tracked_link("", "k", "https://tazabbas.com/projects"), "https://tazabbas.com/projects")
        self.assertEqual(tracked_link("", "a b", "https://tazabbas.com/projects", "utm"),
                         "https://tazabbas.com/projects?utm_source=leadengine&utm_content=a%20b")
        self.assertEqual(tracked_link("", "k", "https://t.com/p?x=1", "utm"), "https://t.com/p?x=1&utm_source=leadengine&utm_content=k")
        self.assertEqual(tracked_link("", "k", "https://tazabbas.com/projects", "redirect"), "https://tazabbas.com/projects")  # no base


class CountyTests(unittest.TestCase):
    def test_counties(self):
        from leadengine import sources
        got = sources.county_cities(["Middlesex", "somerset"])
        names = [c for c, _ in got]
        self.assertIn("Edison", names)
        self.assertIn("Basking Ridge", names)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(st == "NJ" for _, st in got))
        with self.assertRaises(SystemExit):
            sources.county_cities(["Bergen"])


class SegmentTests(unittest.TestCase):
    def test_tiers(self):
        import argparse
        from leadengine.cli import taxonomies_for
        a = argparse.Namespace(taxonomy="", tier="focus")
        self.assertEqual(taxonomies_for(a), ["Cardiovascular Disease", "Ophthalmology"])
        a.tier = "1"
        self.assertIn("Dentist", taxonomies_for(a))
        a.tier = "all"
        self.assertIn("Gastroenterology", taxonomies_for(a))
        a.taxonomy = "Podiatrist, Chiropractor"
        self.assertEqual(taxonomies_for(a), ["Podiatrist", "Chiropractor"])


if __name__ == "__main__":
    unittest.main()
