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


if __name__ == "__main__":
    unittest.main()
