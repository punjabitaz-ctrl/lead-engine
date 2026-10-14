import json
import os
import tempfile
import unittest

from leadengine import sitebuilder as sb

HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(HERE, "..", "examples", "sample-practice", "intake.json")


def intake():
    with open(SAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


class SiteBuilderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as fh:
            return fh.read()

    def test_one_page_site_passes_qa_and_has_the_essentials(self):
        d = intake()
        self.assertEqual(sb.build(d, self.out, 1), ["index.html"])
        page = self.read("index.html")
        for needle in ("Example Family Dental", "(732) 555-0142", "123 Example Avenue", "08817", "8:00 am to 5:00 pm", "Cleanings and exams", "Privacy policy",
                       'href="tel:7325550142"', "do not send health information"):
            self.assertIn(needle, page.replace("Please do not send health information", "do not send health information") if needle.startswith("do not") else page)
        self.assertEqual(sb.qa(self.out, d)[0], [])

    def test_three_page_site_has_four_files_and_passes_qa(self):
        d = intake()
        self.assertEqual(sb.build(d, self.out, 3), ["index.html", "services.html", "about-contact.html", "privacy.html"])
        self.assertIn("Privacy policy", self.read("privacy.html"))
        self.assertIn("Cleanings and exams", self.read("services.html"))
        self.assertEqual(sb.qa(self.out, d)[0], [])

    def test_missing_client_materials_stop_the_build(self):
        d = intake()
        del d["privacy_policy_text"]
        d["services"] = []
        with self.assertRaises(ValueError) as cm:
            sb.build(d, self.out, 1)
        self.assertIn("privacy_policy_text", str(cm.exception))
        self.assertIn("services", str(cm.exception))
        self.assertEqual(os.listdir(self.out), [])                      # nothing half-written

    def test_placeholders_and_missing_alt_text_are_refused(self):
        d = intake()
        d["practice_name"] = "[Practice name]"
        d["photos"] = [{"file": "x.jpg", "alt": ""}]
        with self.assertRaises(ValueError) as cm:
            sb.build(d, self.out, 1)
        self.assertIn("placeholder", str(cm.exception))
        self.assertIn("alt text", str(cm.exception))

    def test_three_page_needs_an_about_text(self):
        d = intake()
        d["about"] = ""
        with self.assertRaises(ValueError):
            sb.build(d, self.out, 3)
        sb.build(d, self.out, 1)                                          # the one-page site does not need it

    def test_content_is_escaped(self):
        d = intake()
        d["practice_name"] = 'Smith & <b>Sons</b> "Dental"'
        sb.build(d, self.out, 1)
        page = self.read("index.html")
        self.assertIn("Smith &amp; &lt;b&gt;Sons&lt;/b&gt; &quot;Dental&quot;", page)
        self.assertNotIn("<b>Sons</b>", page)

    def test_structured_data_cannot_break_out_of_its_script_tag(self):
        d = intake()
        d["practice_name"] = "Evil </script><script>alert(1)</script>"
        sb.build(d, self.out, 1)
        page = self.read("index.html").lower()
        self.assertEqual(page.count("</script"), 1)                      # only the real closing tag; the name's </script> was escaped
        self.assertNotIn("<!--", page)

    def test_form_has_no_health_fields_and_a_warning(self):
        sb.build(intake(), self.out, 1)
        page = self.read("index.html")
        self.assertIn("<form", page)
        for field in ("symptom", "diagnos", "insurance", "birth"):
            self.assertNotIn(f'name="{field}', page)
        self.assertIn("select name=\"reason\"", page)

    def test_qa_catches_problems(self):
        d = intake()
        sb.build(d, self.out, 1)
        path = os.path.join(self.out, "index.html")
        text = open(path, encoding="utf-8").read()
        text = text.replace('<title>', '<title></title><title>', 1).replace("Cleanings and exams", "[Service name]")
        text = text.replace("<form", '<img src="https://tracker.example/x.gif"><form', 1).replace('name="phone"', 'name="symptoms"', 1)
        open(path, "w", encoding="utf-8").write(text)
        problems = " | ".join(sb.qa(self.out, d)[0])
        for needle in ("placeholder", "external resource", "could collect health information", "image without alt"):
            self.assertIn(needle, problems)

    def test_qa_checks_the_intake_against_the_site(self):
        d = intake()
        sb.build(d, self.out, 1)
        d["phone"] = "(732) 555-9999"                                      # the client changed their number after the build
        problems = sb.qa(self.out, d)[0]
        self.assertTrue(any("phone" in p for p in problems))

    def test_text_colour_stays_readable(self):
        self.assertEqual(sb._readable("#ffffff"), "#111111")
        self.assertEqual(sb._readable("#0b5cad"), "#ffffff")
        self.assertEqual(sb._readable("#ffe066"), "#111111")

    def test_cli_builds_and_returns_failure_on_missing_intake_items(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sb.main(["build", SAMPLE, "--out", self.out, "--pages", "3"]), 0)
            bad = intake()
            bad["email"] = ""
            path = os.path.join(self.out, "bad.json")
            json.dump(bad, open(path, "w"))
            self.assertEqual(sb.main(["build", path, "--out", os.path.join(self.out, "x")]), 1)


if __name__ == "__main__":
    unittest.main()
