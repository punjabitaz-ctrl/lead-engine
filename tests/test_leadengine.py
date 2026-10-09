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

    def test_tiers(self):
        fresh = {"hiring": "Y", "sigdate": TODAY - dt.timedelta(days=5), "n_postings": 1}
        mid = {"hiring": "Y", "sigdate": TODAY - dt.timedelta(days=60), "n_postings": 1}
        old = {"hiring": "Y", "sigdate": TODAY - dt.timedelta(days=200), "n_postings": 1}
        self.assertEqual([scoring.tier(x, CFG, TODAY) for x in (fresh, mid, old)], ["hot", "warm", "cold"])


if __name__ == "__main__":
    unittest.main()
