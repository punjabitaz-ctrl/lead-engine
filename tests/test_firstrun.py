"""The one-command first run: demo end to end (no network), sender file, and the stop when the registry is unreachable."""
import json
import os
import tempfile
import unittest

from leadengine import campaign, firstrun


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "campaigns")
        self.lines = []

    def tearDown(self):
        self._tmp.cleanup()

    def demo(self, **kw):
        return firstrun.first_run("demo-nj", root=self.root, demo=True, out=self.lines.append, **kw)

    def test_demo_runs_every_step_offline(self):
        res = self.demo()
        d = campaign.folder("demo-nj", self.root)
        self.assertEqual(len(res["packs"]), 1)
        rows = campaign._read_csv(res["packs"][0])[0]
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(r["Company"].startswith("DEMO ") for r in rows))
        self.assertTrue(all(r["Confidence"] for r in rows))
        self.assertTrue(all(r["Email Status"] == "" for r in rows))          # no email, so no status
        self.assertTrue(os.path.exists(res["report"]))
        self.assertTrue(os.path.exists(res["xlsx"]))
        self.assertTrue(res["sender_problems"])                               # placeholders until the sender file is applied
        text = "\n".join(self.lines)
        self.assertIn("DEMO", text)
        self.assertIn("not websites or emails", text)
        self.assertIn("campaign approve demo-nj", text)
        self.assertTrue(os.path.exists(os.path.join(d, "spec.json")))

    def test_second_run_does_not_repeat_leads(self):
        first = self.demo()
        with self.assertRaises(SystemExit) as cm:                             # the demo source has nothing new to give
            self.demo()
        self.assertIn("already in your review packs", str(cm.exception))
        self.assertEqual(len(campaign._review_packs("demo-nj", self.root)), 1)
        self.assertTrue(first["packs"])

    def test_unreachable_registry_stops_before_creating_anything(self):
        real = firstrun.reachable
        firstrun.reachable = lambda url: False
        try:
            with self.assertRaises(SystemExit) as cm:
                firstrun.first_run("nj-medical", root=self.root, out=self.lines.append)
        finally:
            firstrun.reachable = real
        self.assertIn("not reachable", str(cm.exception))
        self.assertFalse(os.path.exists(campaign.folder("nj-medical", self.root)))

    def test_sender_file_copies_filled_values_only(self):
        self.demo()
        path = os.path.join(self._tmp.name, "sender.json")
        with open("examples/sender_config_example.json", encoding="utf-8") as fh:
            data = json.load(fh)
        data["sender"].update(name="Sam Example", business="Example Studio", address="PO Box 1, Edison, NJ 08817",
                              reply_email="sam@examplestudio.test")
        data["mail"]["from_email"] = "sam@examplestudio.test"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        cpath, skipped = firstrun.apply_sender("demo-nj", path, self.root)
        self.assertIn("sender.offer", skipped)
        self.assertIn("sender.portfolio_url", skipped)
        cfg = campaign._read_json(cpath)
        self.assertEqual(cfg["sender"]["name"], "Sam Example")
        self.assertEqual(cfg["mail"]["from_email"], "sam@examplestudio.test")
        self.assertNotIn("[", cfg["sender"].get("portfolio_url", ""))
        self.assertEqual(firstrun.check_sender("demo-nj", self.root, out=self.lines.append), [])
        self.assertEqual(firstrun.main(["--name", "demo-nj", "--root", self.root, "--check-sender"]), 0)

    def test_sender_file_rejects_other_blocks(self):
        self.demo()
        path = os.path.join(self._tmp.name, "bad.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"sender": {}, "points": {"x": 1}}, fh)
        with self.assertRaises(SystemExit):
            firstrun.apply_sender("demo-nj", path, self.root)

    def test_demo_name_guard(self):
        with self.assertRaises(SystemExit):
            firstrun.main(["--demo", "--name", "nj-medical", "--root", self.root])


if __name__ == "__main__":
    unittest.main()
