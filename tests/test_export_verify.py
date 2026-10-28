"""List exports (CSV, Excel, PDF), accuracy checks and the enrich step. Every network call goes to a stand-in."""
import csv
import datetime as dt
import io
import json
import os
import re
import tempfile
import unittest
import urllib.error
import zipfile

from leadengine import campaign, enrich, listexport, presence, verify

TODAY = dt.date(2026, 10, 28)
GOOD_NPI = "1234567893"          # the CMS example number, with a correct check digit
FIELDS = ["Company", "Website", "Phone", "City", "State", "NPI", "Email", "Email Status", "First Name", "Last Name", "Title",
          "Score", "Grade", "Primary Signal", "Why This Lead", "Notes"]


def write(path, rows, fields=FIELDS):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeNet:
    """DNS over HTTPS and NPPES answers by URL."""

    def __init__(self, mx=None, npi=None, down=False):
        self.mx, self.npi, self.down, self.calls = mx or {}, npi or {}, down, []

    def __call__(self, req, timeout=15):
        url = req.full_url
        self.calls.append(url)
        if self.down:
            raise urllib.error.URLError("network blocked")
        if "dns.google" in url:
            name = re.search(r"name=([^&]+)", url).group(1)
            kind = re.search(r"type=(\w+)", url).group(1)
            v = self.mx.get(name, "ok")
            if v == "nxdomain":
                body = {"Status": 3}
            elif v == "ok" and kind == "MX":
                body = {"Status": 0, "Answer": [{"type": 15, "data": "10 mx." + name}]}
            elif v == "a-only" and kind == "A":
                body = {"Status": 0, "Answer": [{"type": 1, "data": "192.0.2.1"}]}
            else:
                body = {"Status": 0}
            return Resp(json.dumps(body).encode())
        if "npiregistry" in url:
            num = re.search(r"number=(\d+)", url).group(1)
            res = self.npi.get(num)
            return Resp(json.dumps({"results": [res] if res else []}).encode())
        raise AssertionError("unexpected URL " + url)


def sites(table):
    """A website fetcher: url -> (final_url, html) or an exception to raise."""
    def fetch(url, timeout=15):
        v = table.get(url, ("", "<html><title>Welcome</title><p>Family dentistry since 1990.</p></html>"))
        if isinstance(v, Exception):
            raise v
        return (v[0] or url, v[1])
    return fetch


def lead(i, **kw):
    r = {"Company": f"Edison Smile {i}", "Website": f"https://smile{i}.test", "Phone": f"(732) 4{i:02d}-12{i:02d}", "City": "Edison",
         "State": "NJ", "Email": f"dr{i}@smile{i}.test", "Email Status": "Risky", "First Name": "Pat", "Last Name": "Lee",
         "Title": "Owner", "Score": str(90 - i), "Grade": "A" if i < 3 else "B", "Primary Signal": "Hiring", "Why This Lead": "Hiring a hygienist"}
    r.update(kw)
    return r


class OfflineChecks(unittest.TestCase):
    def test_email_rules(self):
        self.assertEqual(verify.email_check("dr.lee@smile.test")[0], "")
        self.assertEqual(verify.email_check("dr..lee@smile.test")[0], "Invalid")
        self.assertEqual(verify.email_check("no-at-sign")[0], "Invalid")
        self.assertEqual(verify.email_check("x@mailinator.com")[0], "Invalid")
        self.assertIn("role address", verify.email_check("info@smile.test")[1][0])
        self.assertIn("free mail", verify.email_check("drlee@gmail.com")[1][0])
        self.assertEqual(verify.email_check("")[1], ["no email"])

    def test_phone_rules(self):
        self.assertEqual(verify.phone_check("1-732-555-0142")[0], "")      # 555-01xx is reserved for fiction
        self.assertEqual(verify.phone_check("732.494.1200")[0], "(732) 494-1200")
        self.assertEqual(verify.phone_check("+1 (732) 494-1200 x12")[0], "(732) 494-1200")
        self.assertIn("area code", verify.phone_check("(132) 494-1200")[1][0])
        self.assertIn("exchange", verify.phone_check("(732) 094-1200")[1][0])
        self.assertIn("10-digit", verify.phone_check("494-1200")[1][0])
        self.assertIn("placeholder", " ".join(verify.phone_check("(222) 222-2222")[1]))

    def test_npi_check_digit(self):
        self.assertTrue(verify.npi_valid(GOOD_NPI))
        self.assertFalse(verify.npi_valid("1234567890"))
        self.assertFalse(verify.npi_valid("12345"))

    def test_row_level_checks(self):
        got = verify.offline(lead(1, Email="dr@othersite.test", State="ZZ", NPI="1234567890", Company="EDISON SMILE DENTAL",
                                  Website="https://www.yelp.com/biz/edison-smile", **{"First Name": "Info"}))
        text = " | ".join(got["issues"])
        self.assertIn("fails its check digit", text)
        self.assertIn("not a US state code", text)
        self.assertIn("capitals", text)
        self.assertIn("listing on www.yelp.com", text)
        self.assertIn("does not look like a person", text)
        mismatch = verify.offline(lead(1, Email="dr@othersite.test"))
        self.assertIn("email domain othersite.test differs from the website smile1.test", mismatch["issues"])

    def test_duplicates_by_key_email_phone_and_name(self):
        rows = [lead(1), lead(2, Email="dr1@smile1.test"), lead(3, Phone="732-401-1201"), lead(4, Company="Edison Smile 1", Website="")]
        d = verify.duplicates(rows)
        self.assertEqual(sorted(d), [1, 2, 3])
        self.assertIn("row 2 (same email)", d[1])
        self.assertIn("same phone", d[2])
        self.assertRegex(d[3], "same (lead key|name and city)")

    def test_confidence_is_bounded_and_ranks(self):
        clean = verify.confidence([], "Valid")
        messy = verify.confidence(["website is down", "NPI is not active in the registry", "no phone"], "Risky")
        self.assertEqual(clean, 100)
        self.assertLess(messy, 50)
        self.assertEqual(verify.confidence(["domain does not exist"] * 5, "Invalid"), 0)


class NetworkChecks(unittest.TestCase):
    def test_mail_domain(self):
        c = verify.Checker(opener=FakeNet({"gone.test": "nxdomain", "nomail.test": "none", "aonly.test": "a-only"}))
        self.assertEqual(c.mail_domain("smile.test"), "ok")
        self.assertEqual(c.mail_domain("gone.test"), "domain does not exist")
        self.assertEqual(c.mail_domain("nomail.test"), "no mail servers")
        self.assertEqual(c.mail_domain("aonly.test"), "ok")             # mail can be delivered to the A record

    def test_blocked_network_never_gives_a_verdict(self):
        c = verify.Checker(opener=FakeNet(down=True), fetch=sites({"https://a.test": urllib.error.URLError("timed out")}))
        self.assertEqual(c.mail_domain("smile.test"), verify.NOT_CHECKED)
        self.assertEqual(c.npi(GOOD_NPI), verify.NOT_CHECKED)
        self.assertEqual(c.website("https://a.test")[0], verify.NOT_CHECKED)
        self.assertEqual(c.failures, 3)

    def test_website_states(self):
        c = verify.Checker(fetch=sites({
            "https://parked.test": ("", "<html>This domain is for sale! Buy this domain at hugedomains</html>"),
            "https://moved.test": ("https://www.bigchain.test/locations/edison", "<html>Big Chain Dental</html>"),
            "https://www.ok.test": ("https://ok.test/", "<html>Welcome</html>"),
            "https://gone.test": urllib.error.HTTPError("https://gone.test", 404, "Not Found", {}, None),
            "https://nodns.test": urllib.error.URLError("[Errno -2] Name or service not known")}))
        self.assertEqual(c.website("https://parked.test")[0], "parked")
        self.assertEqual(c.website("https://moved.test")[0], "redirects to bigchain.test")
        self.assertEqual(c.website("https://www.ok.test")[0], "live")
        self.assertEqual(c.website("https://gone.test")[0], "down")
        self.assertEqual(c.website("https://nodns.test")[0], "down")

    def test_npi_registry(self):
        net = FakeNet(npi={GOOD_NPI: {"basic": {"status": "A", "organization_name": "EDISON SMILE 1 LLC"}},
                           "1245319599": {"basic": {"status": "D", "last_name": "LEE"}}})
        c = verify.Checker(opener=net)
        self.assertEqual(c.npi(GOOD_NPI, "Edison Smile 1"), "active")
        self.assertEqual(c.npi("1245319599"), "deactivated")
        self.assertEqual(c.npi("1003000126"), "not found")
        self.assertTrue(c.npi(GOOD_NPI, "Totally Different Ortho").startswith("name differs"))

    def test_paid_verifier_needs_a_key_and_respects_the_limit(self):
        os.environ.pop("ZEROBOUNCE_API_KEY", None)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                verify.PaidVerifier("zerobounce", 5, d)
            os.environ["ZEROBOUNCE_API_KEY"] = "test-key"
            try:
                seen = []
                def opener(req, timeout=15):
                    seen.append(req.full_url)
                    return Resp(json.dumps({"status": "valid" if "good" in req.full_url else "invalid"}).encode())
                p = verify.PaidVerifier("zerobounce", 2, d, opener=opener)
                self.assertEqual(p.check("good@smile.test"), "Valid")
                self.assertEqual(p.check("bad@smile.test"), "Invalid")
                self.assertEqual(p.check("good@smile.test"), "Valid")     # cached, not billed again
                self.assertEqual(p.check("third@smile.test"), "")         # limit reached: no call
                self.assertEqual(len(seen), 2)
            finally:
                os.environ.pop("ZEROBOUNCE_API_KEY", None)


class CampaignBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "campaigns")
        self.state = os.path.join(self._tmp.name, "state")
        campaign.init("nj", "NJ", counties=["Middlesex"], root=self.root)
        self.d = campaign.folder("nj", self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def approved(self, rows):
        for r in rows:
            r["Lead Key"] = campaign.lead_key(r)
        write(os.path.join(self.d, "approved.csv"), rows, FIELDS + ["Lead Key"] + [k for k in rows[0] if k not in FIELDS and k != "Lead Key"])


class FakeFinder:
    def __init__(self, found):
        self.found, self.asked = found, []

    def find(self, website, first="", last=""):
        self.asked.append(website)
        return self.found.get(website, {"email": "", "estatus": "", "phone": "", "linkedin": "", "page": "", "note": "no address published on the site"})


class EnrichTests(CampaignBase):
    def run_enrich(self, net=None, fetch=None, finder=None, steps=enrich.FREE, **kw):
        checker = verify.Checker(opener=net or FakeNet(), fetch=fetch or sites({}), today=TODAY)
        return enrich.run("nj", self.root, "approved", steps, checker=checker, finder=finder or FakeFinder({}), today=TODAY,
                          state_dir=self.state, **kw)

    def test_enrich_flags_without_dropping_rows_and_keeps_a_backup(self):
        rows = [lead(1, NPI=GOOD_NPI), lead(2, Email="dr2@gone.test"), lead(3, Website="https://parked.test"), lead(4, Email="", Phone="12")]
        self.approved(rows)
        net = FakeNet({"gone.test": "nxdomain"}, npi={GOOD_NPI: {"basic": {"status": "A", "organization_name": "Edison Smile 1"}}})
        res = self.run_enrich(net, sites({"https://parked.test": ("", "<html>buy this domain</html>")}))
        out = {r["Company"]: r for r in read(os.path.join(self.d, "approved.csv"))}
        self.assertEqual(len(out), 4)
        self.assertTrue(os.path.exists(os.path.join(self.d, ".backup", "approved.csv.bak")))
        self.assertEqual(out["Edison Smile 1"]["NPI Check"], "active")
        self.assertEqual(out["Edison Smile 1"]["Email Check"], "domain receives mail")
        self.assertEqual(out["Edison Smile 1"]["Email Status"], "Risky")          # a free check never upgrades to Valid
        self.assertEqual(out["Edison Smile 1"]["Last Verified"], TODAY.isoformat())
        self.assertEqual(out["Edison Smile 2"]["Email Status"], "Invalid")
        self.assertIn("domain does not exist", out["Edison Smile 2"]["Issues"])
        self.assertEqual(out["Edison Smile 3"]["Website Check"], "parked")
        self.assertIn("website is parked", out["Edison Smile 3"]["Issues"])
        self.assertIn("10-digit", out["Edison Smile 4"]["Issues"])
        self.assertGreater(int(out["Edison Smile 1"]["Confidence"]), int(out["Edison Smile 2"]["Confidence"]))
        self.assertTrue(os.path.exists(res["report"]))
        with open(res["report"], encoding="utf-8") as fh:
            report = fh.read()
        self.assertIn("4 rows", report)
        self.assertIn("Lowest confidence", report)

    def test_contacts_step_fills_gaps_only(self):
        self.approved([lead(1, Email="", Phone="", **{"Email Status": ""}), lead(2)])
        finder = FakeFinder({"https://smile1.test": {"email": "office@smile1.test", "estatus": "Risky", "phone": "(732) 494-1200",
                                                     "linkedin": "https://www.linkedin.com/company/smile1", "page": "https://smile1.test/contact", "note": ""}})
        self.run_enrich(finder=finder)
        self.assertEqual(finder.asked, ["https://smile1.test"])                  # row 2 already had an email
        out = read(os.path.join(self.d, "approved.csv"))
        self.assertEqual(out[0]["Email"], "office@smile1.test")
        self.assertEqual(out[0]["Phone (formatted)"], "(732) 494-1200")
        self.assertIn("Contact found on: https://smile1.test/contact", out[0]["Notes"])

    def test_blocked_network_says_not_checked_and_keeps_status(self):
        self.approved([lead(1)])
        res = self.run_enrich(FakeNet(down=True), sites({"https://smile1.test": urllib.error.URLError("timed out")}))
        out = read(os.path.join(self.d, "approved.csv"))[0]
        self.assertEqual(out["Email Check"], verify.NOT_CHECKED)
        self.assertEqual(out["Website Check"], verify.NOT_CHECKED)
        self.assertEqual(out["Email Status"], "Risky")
        self.assertEqual(res["network_failures"], 2)

    def test_quality_is_read_only_and_keeps_earlier_results(self):
        self.approved([lead(1, Website="https://parked.test"), lead(2)])
        self.run_enrich(fetch=sites({"https://parked.test": ("", "<html>buy this domain</html>")}))
        path = os.path.join(self.d, "approved.csv")
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        res = enrich.run("nj", self.root, "approved", (), today=TODAY + dt.timedelta(days=1), write=False, state_dir=self.state)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)
        self.assertEqual(res["summary"]["rows"], 2)
        self.assertIn("website is parked", res["summary"]["issues"])

    def test_enriching_review_packs_does_not_create_extra_packs(self):
        rows = [lead(1), lead(2)]
        for r in rows:
            r["Lead Key"] = campaign.lead_key(r)
        write(os.path.join(self.d, "review", "pack-01.csv"), rows, FIELDS + ["Lead Key", "Decision"])
        checker = verify.Checker(opener=FakeNet(), fetch=sites({}), today=TODAY)
        enrich.run("nj", self.root, "review", enrich.FREE, checker=checker, finder=FakeFinder({}), today=TODAY, state_dir=self.state)
        self.assertEqual([os.path.basename(p) for p in campaign._review_packs("nj", self.root)], ["pack-01.csv"])
        self.assertEqual(len(listexport.load("nj", self.root, "review")[0]), 2)

    def test_stale_rows_are_flagged(self):
        self.approved([lead(1, **{"Last Verified": "2026-06-01"})])
        res = enrich.run("nj", self.root, "approved", (), today=TODAY, write=False, state_dir=self.state)
        self.assertIn("not verified in the last 90 days", res["summary"]["issues"])

    def test_verify_step_requires_a_paid_verifier(self):
        self.approved([lead(1)])
        with self.assertRaises(SystemExit):
            enrich.run("nj", self.root, "approved", ("verify",), today=TODAY, state_dir=self.state)
        with self.assertRaises(SystemExit):
            enrich.run("nj", self.root, "approved", ("nonsense",), today=TODAY, state_dir=self.state)

    def test_paid_check_is_the_only_way_to_valid(self):
        self.approved([lead(1), lead(2, Email="dr2@gone.test")])

        class Paid:
            name, used = "zerobounce", 0
            def check(self, email):
                self.used += 1
                return "Valid"
        paid = Paid()
        self.run_enrich(FakeNet({"gone.test": "nxdomain"}), steps=enrich.FREE + ("verify",), paid=paid)
        out = read(os.path.join(self.d, "approved.csv"))
        self.assertEqual(out[0]["Email Status"], "Valid")
        self.assertEqual(out[1]["Email Status"], "Invalid")                     # no paid check on a dead domain
        self.assertEqual(paid.used, 1)


class ExportTests(CampaignBase):
    def setUp(self):
        super().setUp()
        self.approved([lead(i) for i in range(1, 6)] + [lead(6, Company="=HYPERLINK(\"http://evil.test\")", Email="x@evil.test",
                                                              Website="https://evil.test", Phone="+1 732 494 1266")])
        write(os.path.join(self.d, "suppress.csv"), [{"value": "dr5@smile5.test"}], ["value"])

    def export(self, *args):
        return listexport.main(["nj", *args], self.root)

    def test_csv_export_filters_suppresses_and_defuses_formulas(self):
        out = os.path.join(self._tmp.name, "a.csv")
        self.export("--format", "csv", "--out", out)
        with open(out, "rb") as fh:
            self.assertTrue(fh.read().startswith(b"\xef\xbb\xbf"))
        rows = read(out)
        self.assertEqual(len(rows), 5)                                           # dr5 is suppressed
        self.assertNotIn("dr5@smile5.test", [r["Email"] for r in rows])
        evil = [r for r in rows if "HYPERLINK" in r["Company"]][0]
        self.assertTrue(evil["Company"].startswith("'="))
        self.assertTrue(evil["Phone"].startswith("'+"))
        self.assertEqual(list(rows[0])[:5], ["Company", "First Name", "Last Name", "Title", "Email"])
        self.export("--format", "csv", "--out", out, "--grade", "a", "--include-suppressed")
        self.assertEqual(len(read(out)), 2)
        self.export("--format", "csv", "--out", out, "--columns", "Company,Email", "--min-score", "87")
        got = read(out)
        self.assertEqual(list(got[0]), ["Company", "Email"])
        self.assertEqual([r["Company"] for r in got], ["Edison Smile 1", "Edison Smile 2", "Edison Smile 3"])
        with self.assertRaises(SystemExit):
            self.export("--format", "csv", "--columns", "Company,Nope")

    def test_xlsx_is_a_valid_workbook(self):
        out = os.path.join(self._tmp.name, "a.xlsx")
        self.export("--format", "xlsx", "--out", out, "--columns", "full")
        with zipfile.ZipFile(out) as z:
            self.assertIsNone(z.testzip())
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
            self.assertIn('state="frozen"', sheet)
            self.assertIn("<autoFilter", sheet)
            self.assertIn("<v>89</v>", sheet)                                    # Score is numeric
            self.assertIn("=HYPERLINK", sheet)                                   # kept as text, never a formula
            self.assertNotIn("<f>", sheet)
            self.assertIn("About this export", z.read("xl/worksheets/sheet2.xml").decode())
        try:
            import openpyxl
        except ImportError:
            return
        wb = openpyxl.load_workbook(out)
        ws = wb["Leads"]
        self.assertEqual(ws.max_row, 6)
        header = [c.value for c in ws[1]]
        self.assertEqual(ws.cell(2, header.index("Score") + 1).value, 89)
        self.assertEqual(ws.freeze_panes, "A2")
        self.assertIn("Rows exported", [c.value for c in wb["About"]["A"]])

    def test_pdf_is_well_formed_and_paginates(self):
        self.approved([lead(i, **{"Why This Lead": "A very long reason " * 20, "Company": f"Practice Ñame {i}"}) for i in range(1, 121)])
        out = os.path.join(self._tmp.name, "a.pdf")
        self.export("--format", "pdf", "--out", out)
        with open(out, "rb") as fh:
            pdf = fh.read()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        pages = int(re.search(rb"/Type /Pages /Kids \[[^\]]*\] /Count (\d+)", pdf).group(1))
        self.assertGreater(pages, 2)
        self.assertTrue(b"page 1 of %d" % pages in pdf)
        self.assertTrue(b"Practice \xd1ame 1" in pdf)                          # WinAnsi encoding of the accent
        self.export("--format", "pdf", "--out", out, "--columns", "Company,Why This Lead,Email")
        with open(out, "rb") as fh:
            self.assertTrue(b"...) Tj" in fh.read())                           # long cells are cut
        # every xref offset points at its object
        start = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
        table = pdf[start:].split(b"\n")
        count = int(table[1].split()[1])
        for n, line in enumerate(table[3:3 + count - 1], 1):
            off = int(line.split()[0])
            self.assertTrue(pdf[off:].startswith(b"%d 0 obj" % n), n)
        try:
            import pypdf
        except ImportError:
            return
        self.assertEqual(len(pypdf.PdfReader(out).pages), pages)

    def test_fit_and_widths(self):
        self.assertEqual(listexport.fit("short", 100, 8), "short")
        cut = listexport.fit("a much longer piece of text than fits", 40, 8)
        self.assertTrue(cut.endswith("..."))
        self.assertLessEqual(listexport.text_width(cut, 8), 40)

    def test_standalone_file_export_and_empty_result(self):
        src = os.path.join(self._tmp.name, "leads.csv")
        write(src, [lead(1), lead(2)])
        self.assertEqual(listexport.main([src, "--format", "xlsx"], campaign_mode=False), 0)
        self.assertTrue(os.path.exists(os.path.join(self._tmp.name, "leads-export.xlsx")))
        with self.assertRaises(SystemExit):
            listexport.main([src, "--format", "csv", "--grade", "Z"], campaign_mode=False)

    def test_review_and_all_lists_do_not_repeat_leads(self):
        rows = read(os.path.join(self.d, "approved.csv"))
        write(os.path.join(self.d, "review", "pack-01.csv"), rows[:3], list(rows[0]))
        got, _ = listexport.load("nj", self.root, "all")
        self.assertEqual(len(got), 6)
        got, label = listexport.load("nj", self.root, "review")
        self.assertEqual((len(got), label), (3, "review"))


class PlacesCacheTTL(unittest.TestCase):
    def test_entries_expire_after_30_days(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "presence_cache.json"), "w", encoding="utf-8") as fh:
                json.dump({"old|edison|NJ": {"hasweb": "Y", "hasgbp": "Y", "reviews": 3, "_at": "2026-09-01"},
                           "new|edison|NJ": {"hasweb": "N", "hasgbp": "Y", "reviews": 1, "_at": "2026-10-20"},
                           "undated|edison|NJ": {"hasweb": "Y", "hasgbp": "Y", "reviews": 9}}, fh)
            c = presence.PlacesChecker(d, today=TODAY)
            self.assertEqual(sorted(c.cache), ["new|edison|NJ"])
            self.assertEqual(c.check("New", "Edison", "NJ"), {"hasweb": "N", "hasgbp": "Y", "reviews": 1})


class CLITests(CampaignBase):
    def test_campaign_dispatch(self):
        self.approved([lead(1)])
        out = os.path.join(self._tmp.name, "x.csv")
        self.assertEqual(campaign.main(["--root", self.root, "export", "nj", "--format", "csv", "--out", out]), 0)
        self.assertEqual(len(read(out)), 1)
        self.assertEqual(campaign.main(["--root", self.root, "quality", "nj"]), 0)
        self.assertTrue(any(f.startswith("quality-approved-") for f in os.listdir(self.d)))


if __name__ == "__main__":
    unittest.main()
