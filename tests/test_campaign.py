import csv
import datetime as dt
import json
import os
import tempfile
import unittest

from leadengine import campaign, cli, geo, packs

START = dt.date(2026, 10, 12)          # a Monday


def write(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


class GeoPackTests(unittest.TestCase):
    def test_resolve_counties_cities_state(self):
        got = geo.resolve({"state": "NJ", "counties": ["Somerset"]})
        self.assertIn(("Basking Ridge", "NJ"), got)
        self.assertEqual(geo.resolve({"cities": ["Tampa, FL", "Austin, tx"]}), [("Tampa", "FL"), ("Austin", "TX")])
        self.assertGreater(len(geo.resolve({"state": "NJ"})), 40)
        with self.assertRaises(SystemExit):
            geo.resolve({"state": "ZZ", "counties": ["X"]})
        with self.assertRaises(SystemExit):
            geo.resolve({"state": "NJ", "counties": ["Bergen"]})

    def test_packs(self):
        self.assertTrue({"healthcare-practices", "local-services", "tech-hiring"} <= set(packs.available()))
        hp = packs.load("healthcare-practices")
        self.assertEqual(packs.terms(hp, "taxonomies"), ["Cardiovascular Disease", "Ophthalmology"])
        everything = packs.terms(hp, "taxonomies", ["all"])
        self.assertEqual(len(everything), len(set(everything)))
        self.assertIn("plumber", packs.terms(packs.load("local-services"), "places_queries"))
        with self.assertRaises(SystemExit):
            packs.load("nope")


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.spec, problems = campaign.init("nj-test", "NJ", counties=["Middlesex"], root=self.root)
        self.assertEqual(problems, [])
        self.d = campaign.folder("nj-test", self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def sender(self, ok=True):
        cfg = json.load(open(os.path.join(self.d, "config.json")))
        if ok:
            cfg["sender"].update(name="Sam Example", business="Example Studio", address="1 Main St, Edison, NJ 08817", offer="We build websites.")
        json.dump(cfg, open(os.path.join(self.d, "config.json"), "w"))

    def pack_rows(self, n=3):
        fields = ["Company", "Website", "City", "Email", "Email Status", "Phone", "First Name", "Last Name", "LinkedIn URL", "Draft Subject", "Draft Email 1",
                  "Lead Key", "Decision", "Reviewer Notes"]
        rows = []
        for i in range(n):
            r = dict.fromkeys(fields, "")
            r.update(Company=f"Practice {i}", City="Edison", Email=f"doc{i}@practice{i}.test", Phone=f"555-000{i}", **{"LinkedIn URL": f"https://linkedin.test/in/doc{i}"})
            r.update({"Draft Subject": "Hello", "Draft Email 1": "Hi.\nIf you'd rather not hear from me, reply \"no thanks\"."})
            r["Lead Key"] = campaign.lead_key(r)
            r["Decision"] = "Keep"
            rows.append(r)
        return rows, fields

    def test_init_validate_and_bad_specs(self):
        self.assertEqual(campaign.validate(self.spec), [])
        bad = json.loads(json.dumps(self.spec))
        bad["geography"]["counties"] = ["Atlantis"]
        bad["tiers"] = ["tier9"]
        bad["sources"] = ["scrape-everything"]
        bad["stages"] = [0]
        bad["outreach"]["sequence"][2]["day"] = 1
        found = " ".join(campaign.validate(bad))
        for needle in ("Atlantis", "tier9", "scrape-everything", "stages", "step 3"):
            self.assertIn(needle, found)
        with self.assertRaises(SystemExit):
            campaign.init("nj-test", "NJ", root=self.root)       # already exists
        with self.assertRaises(SystemExit):
            campaign.init("Bad Name", "NJ", root=self.root)

    def test_blockers_and_status_flow(self):
        st = campaign.status("nj-test", self.root)
        self.assertEqual(st["stages"]["discover"], "ready")
        self.assertIn("agent", st["next_action"])
        spec = campaign.load("nj-test", self.root)
        spec["sources"] = ["places"]
        json.dump(spec, open(os.path.join(self.d, "spec.json"), "w"))
        old = os.environ.pop("GOOGLE_PLACES_API_KEY", None)
        try:
            self.assertTrue(campaign.blockers(spec))
            self.assertEqual(campaign.status("nj-test", self.root)["stages"]["discover"], "blocked")
            with self.assertRaises(SystemExit):
                campaign.run_discover("nj-test", self.root)
        finally:
            if old:
                os.environ["GOOGLE_PLACES_API_KEY"] = old

    def test_review_pack_from_engine_output_then_approve(self):
        import contextlib
        import io
        postings = os.path.join(os.path.dirname(__file__), "..", "examples", "postings_example.csv")
        out = os.path.join(self.d, "runs")
        args = cli.build_parser().parse_args(["run", "--source", "csv", "--postings", postings, "--city", "Example City, ST", "--target", "2",
                                              "--signal", "any", "--fresh", "--no-prompt", "--out", out, "--template", "none.xlsx"])
        with contextlib.redirect_stdout(io.StringIO()):
            written = cli.run(args)
        self.assertEqual(len(written), 1)
        pack = campaign.make_review_pack("nj-test", written[0], self.root)
        rows, fields = campaign._read_csv(pack)
        self.assertEqual(len(rows), 2)
        self.assertTrue({"Lead Key", "Decision", "Reviewer Notes"} <= set(fields))
        rows[0]["Decision"], rows[1]["Decision"] = "keep", "DROP"
        campaign._write_csv(pack, rows, fields)
        self.assertEqual(campaign.approve("nj-test", pack, self.root)["Keep"], 1)
        again = campaign.approve("nj-test", pack, self.root)          # idempotent
        self.assertEqual(again["Keep"], 1)
        self.assertEqual(len(campaign._read_csv(os.path.join(self.d, "approved.csv"))[0]), 1)
        self.assertEqual(len(campaign._read_csv(os.path.join(self.d, "rejected.csv"))[0]), 1)
        self.assertEqual(campaign.status("nj-test", self.root)["stages"]["outreach_plan"], "ready")

    def test_approve_rejects_bad_input(self):
        rows, fields = self.pack_rows(2)
        rows[1]["Decision"] = "maybe"
        path = os.path.join(self.root, "x.csv")
        write(path, rows, fields)
        with self.assertRaises(SystemExit) as cm:
            campaign.approve("nj-test", path, self.root)
        self.assertIn("row 3", str(cm.exception))
        write(path, rows, [f for f in fields if f != "Lead Key"])
        with self.assertRaises(SystemExit):
            campaign.approve("nj-test", path, self.root)

    def test_unsure_stays_pending_until_decided(self):
        rows, fields = self.pack_rows(1)
        rows[0]["Decision"] = "Unsure"
        path = os.path.join(self.root, "y.csv")
        write(path, rows, fields)
        campaign.approve("nj-test", path, self.root)
        self.assertEqual(len(campaign._read_csv(os.path.join(self.d, "pending.csv"))[0]), 1)
        rows[0]["Decision"] = "Keep"
        write(path, rows, fields)
        campaign.approve("nj-test", path, self.root)
        self.assertEqual(campaign._read_csv(os.path.join(self.d, "pending.csv"))[0], [])

    def approved(self, n):
        rows, fields = self.pack_rows(n)
        write(os.path.join(self.d, "approved.csv"), rows, fields)

    def test_outreach_blocked_until_sender_filled(self):
        self.approved(1)
        with self.assertRaises(SystemExit) as cm:
            campaign.plan_outreach("nj-test", START, self.root)
        self.assertIn("sender", str(cm.exception))
        self.sender()
        out, n, skipped, block, warn = campaign.plan_outreach("nj-test", START, self.root)
        self.assertEqual((n, block), (5, []))
        self.assertTrue(any("Do-Not-Call" in w for w in warn))

    def test_windows_on_tasks(self):
        self.sender()
        self.approved(1)
        out, *_ = campaign.plan_outreach("nj-test", START, self.root)
        tasks = {t["Channel"]: t for t in campaign._read_csv(out)[0]}
        self.assertIn("do not send at night", tasks["email"]["Window"])
        self.assertIn("call Fri 10:00-15:00", tasks["phone"]["Window"])
        self.assertNotIn("NEEDS", tasks["phone"]["Window"])
        self.assertEqual(dt.date.fromisoformat(tasks["phone"]["Date"]).weekday(), 4)               # calls land on Fridays only
        spec = campaign.load("nj-test", self.root)
        spec["outreach"]["call_window"] = {"days": ["Tue"], "start": "09:00", "end": "17:00"}      # not inside any daytime block
        self.assertIn("NEEDS A DAYTIME BLOCK", campaign.window_for(spec, "phone"))
        self.assertTrue(any("daytime blocks" in x for x in campaign.offer_warnings(spec)))
        self.assertIn("evening", tasks["linkedin"]["Window"])

    def test_outreach_caps_weekends_spacing(self):
        self.sender()
        spec = campaign.load("nj-test", self.root)
        spec["outreach"]["daily_caps"]["email"] = 2
        json.dump(spec, open(os.path.join(self.d, "spec.json"), "w"))
        self.approved(3)
        out, n, skipped, _, _ = campaign.plan_outreach("nj-test", START, self.root)
        tasks = campaign._read_csv(out)[0]
        for t in tasks:
            self.assertLess(dt.date.fromisoformat(t["Date"]).weekday(), 5)
        per_day = {}
        for t in tasks:
            if t["Channel"] == "email":
                per_day[t["Date"]] = per_day.get(t["Date"], 0) + 1
        self.assertLessEqual(max(per_day.values()), 2)
        first = [t for t in tasks if t["Channel"] == "email" and t["Step"] == "1"]
        self.assertEqual(sorted(t["Date"] for t in first), ["2026-10-12", "2026-10-12", "2026-10-13"])   # cap of 2 pushes the third lead
        self.assertTrue(all(t["Draft"] for t in first))
        self.assertTrue(all(t["Approved to send (Y/N)"] == "" for t in tasks))

    def test_second_plan_only_covers_new_leads_and_shares_caps(self):
        self.sender()
        spec = campaign.load("nj-test", self.root)
        spec["outreach"]["daily_caps"]["email"] = 3
        json.dump(spec, open(os.path.join(self.d, "spec.json"), "w"))
        self.approved(2)
        campaign.plan_outreach("nj-test", START, self.root)
        with self.assertRaises(SystemExit):                       # nothing new yet
            campaign.plan_outreach("nj-test", START, self.root)
        rows, fields = self.pack_rows(4)
        write(os.path.join(self.d, "approved.csv"), rows, fields)    # two old leads plus two new ones
        out, n, _, _, _ = campaign.plan_outreach("nj-test", START, self.root)
        tasks = campaign._read_csv(out)[0]
        self.assertEqual({t["Company"] for t in tasks}, {"Practice 2", "Practice 3"})
        first = sorted(t["Date"] for t in tasks if t["Channel"] == "email" and t["Step"] == "1")
        self.assertEqual(first, ["2026-10-12", "2026-10-13"])        # 2 already planned that day, cap 3 leaves one slot

    def test_suppression_and_missing_contacts(self):
        self.sender()
        rows, fields = self.pack_rows(3)
        rows[1]["Email"] = ""
        rows[1]["Phone"] = ""
        write(os.path.join(self.d, "approved.csv"), rows, fields)
        write(os.path.join(self.d, "suppress.csv"), [{"value": "practice0.test"}], ["value"])      # opt-out by domain
        out, n, skipped, _, _ = campaign.plan_outreach("nj-test", START, self.root)
        companies = {t["Company"] for t in campaign._read_csv(out)[0]}
        self.assertNotIn("Practice 0", companies)
        self.assertIn("Practice 2", companies)
        self.assertTrue(any(c == "Practice 0" and why == "suppressed" for c, why in skipped))
        self.assertTrue(any(c == "Practice 1" for c, _ in skipped))
        self.assertNotIn("Practice 1", {t["Company"] for t in campaign._read_csv(out)[0] if t["Channel"] in ("email", "phone")})

    def test_missing_opt_out_blocks(self):
        self.sender()
        rows, fields = self.pack_rows(1)
        rows[0]["Draft Email 1"] = "Buy now."
        write(os.path.join(self.d, "approved.csv"), rows, fields)
        with self.assertRaises(SystemExit):
            campaign.plan_outreach("nj-test", START, self.root)

    def test_audit_log(self):
        lines = [json.loads(x) for x in open(os.path.join(self.d, "audit.log"))]
        self.assertEqual(lines[0]["event"], "init")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        campaign.init("nj-test", "NJ", counties=["Middlesex"], root=self.root)
        self.d = campaign.folder("nj-test", self.root)
        rows = [{"Lead Key": f"k{i}", "Company": f"Practice {i}", "First Name": "Pat", "Last Name": "Lee", "Source": "NPPES", "Primary Signal": "No Presence"} for i in range(4)]
        write(os.path.join(self.d, "approved.csv"), rows, list(rows[0]))
        self.day = dt.date(2026, 10, 14)          # a Wednesday

    def tearDown(self):
        self._tmp.cleanup()

    def spec_edit(self, fn):
        spec = campaign.load("nj-test", self.root)
        fn(spec)
        with open(os.path.join(self.d, "spec.json"), "w") as fh:
            json.dump(spec, fh)

    def won(self, pid, product="page1", company=None, **kw):
        from leadengine import pipeline
        pipeline.add_deal("nj-test", product, company=company or f"Co {pid}", root=self.root, today=self.day, **kw)
        return pipeline.move_deal("nj-test", pid, "Won", root=self.root, today=self.day)

    def test_defaults_match_the_offer(self):
        o = campaign.load("nj-test", self.root)["offer"]
        self.assertEqual([(p["id"], p["price"], p["payment"]["type"]) for p in o["products"]], [("page1", 250, "full_upfront"), ("page3", 500, "deposit")])
        self.assertEqual([(p["id"], p["price"], p["changes_per_month"], p["max_minutes_per_change"], p["monthly_minutes_cap"]) for p in o["plans"]],
                         [("care9", 9.99, 0, 0, 0), ("care20", 20, 1, 30, 30), ("care50", 50, 5, 190, 240)])
        self.assertFalse(o["plan_terms"]["rollover"])
        self.assertEqual((o["capacity_per_week"], o["in_person_min_monthly_value"]), (10, 5000))
        self.assertEqual(campaign.validate(campaign.load("nj-test", self.root)), [])

    def test_plan_warnings(self):
        w = " ".join(campaign.offer_warnings(campaign.load("nj-test", self.root)))
        self.assertIn("plan care50 ($50/mo): worst case 4.0 h of work a month = $12.50/h", w)      # capped at 4 hours, still under $50/h
        self.assertIn("$200/mo", w)
        self.assertIn("plan care20", w)                                                           # 30 minutes for $20 = $40/h
        self.assertNotIn("plan care9", w)
        self.assertIn("add-on privacy-policy has no price", w)
        self.assertNotIn("operator hours are not set", w)                                           # 2 h x 5 nights
        self.assertNotIn("daytime blocks", w)                                                      # the Friday 10-3 block covers calls
        self.assertNotIn("15.8 h", w)

    def test_uncapped_plan_is_flagged(self):
        spec = campaign.load("nj-test", self.root)
        spec["offer"]["plans"][1]["max_minutes_per_change"] = None
        self.assertIn("no time limit per change", " ".join(campaign.offer_warnings(spec)))

    def test_effective_capacity_follows_your_hours(self):
        spec = campaign.load("nj-test", self.root)
        self.assertEqual(campaign.effective_capacity(spec), 2)                   # 2 h x 5 nights = 10 h x 60% / 3 h = 2 sites
        spec["operator"]["hours_per_week"] = None
        spec["operator"]["nights_per_week"] = spec["operator"]["hours_per_night"] = 0
        self.assertEqual(campaign.effective_capacity(spec), 10)                  # hours unknown: the stated limit
        spec["operator"]["hours_per_week"] = 10
        self.assertEqual(campaign.effective_capacity(spec), 2)
        spec["operator"]["hours_per_week"] = 200
        self.assertEqual(campaign.effective_capacity(spec), 10)                  # never above the stated limit

    def test_only_approved_leads_enter(self):
        from leadengine import pipeline
        with self.assertRaises(SystemExit):
            pipeline.add_deal("nj-test", "page1", lead_key="nope", root=self.root)
        d = pipeline.add_deal("nj-test", "page1", lead_key="k0", root=self.root, today=self.day)
        self.assertEqual((d["Company"], d["Source"], d["Signal"]), ("Practice 0", "NPPES", "No Presence"))
        with self.assertRaises(SystemExit):
            pipeline.add_deal("nj-test", "gold-plated", company="X", root=self.root)
        with self.assertRaises(SystemExit):
            pipeline.add_deal("nj-test", "page1", company="X", plan="platinum", root=self.root)

    def test_won_defaults_and_lost_needs_reason(self):
        from leadengine import pipeline
        pipeline.add_deal("nj-test", "page3", plan="care20", lead_key="k0", root=self.root, today=self.day)
        with self.assertRaises(SystemExit):
            pipeline.move_deal("nj-test", "D001", "Lost", root=self.root)
        d, _ = pipeline.move_deal("nj-test", "D001", "Won", root=self.root, today=self.day)
        self.assertEqual((float(d["One-time $"]), float(d["Monthly $"])), (500.0, 20.0))     # plan price becomes the monthly value
        with self.assertRaises(SystemExit):
            pipeline.move_deal("nj-test", "D001", "Shipped", root=self.root)
        with self.assertRaises(SystemExit):
            pipeline.move_deal("nj-test", "D001", "In build", root=self.root)               # only `start` may do this

    def test_cannot_start_unpaid_or_without_intake(self):
        from leadengine import pipeline
        self.won("D001", "page1")
        with self.assertRaises(SystemExit) as cm:
            pipeline.start_work("nj-test", "D001", root=self.root, today=self.day)
        self.assertIn("$0.00 received, $250.00 required", str(cm.exception))
        self.assertIn("intake", str(cm.exception))
        pipeline.record_payment("nj-test", "D001", 250, root=self.root)
        with self.assertRaises(SystemExit) as cm:
            pipeline.start_work("nj-test", "D001", root=self.root, today=self.day)
        self.assertNotIn("payment", str(cm.exception))
        pipeline.mark_intake("nj-test", "D001", root=self.root)
        deal = pipeline.start_work("nj-test", "D001", root=self.root, today=self.day)
        self.assertEqual((deal["Stage"], deal["Start date"]), ("In build", "2026-10-14"))

    def test_three_page_needs_fifty_percent_deposit(self):
        from leadengine import pipeline
        self.won("D001", "page3")
        pipeline.mark_intake("nj-test", "D001", root=self.root)
        pipeline.record_payment("nj-test", "D001", 249.99, root=self.root)
        with self.assertRaises(SystemExit) as cm:
            pipeline.start_work("nj-test", "D001", root=self.root, today=self.day)
        self.assertIn("$250.00 required", str(cm.exception))
        pipeline.record_payment("nj-test", "D001", 0.01, root=self.root)
        self.assertEqual(pipeline.start_work("nj-test", "D001", root=self.root, today=self.day)["Stage"], "In build")

    def test_only_won_deals_can_start(self):
        from leadengine import pipeline
        pipeline.add_deal("nj-test", "page1", company="Early Co", root=self.root, today=self.day)
        pipeline.record_payment("nj-test", "D001", 250, root=self.root)
        pipeline.mark_intake("nj-test", "D001", root=self.root)
        with self.assertRaises(SystemExit) as cm:
            pipeline.start_work("nj-test", "D001", root=self.root, today=self.day)
        self.assertIn("must be Won", str(cm.exception))

    def test_funnel_counts_lost_at_furthest_stage(self):
        from leadengine import pipeline
        for i in range(3):
            pipeline.add_deal("nj-test", "page1", lead_key=f"k{i}", root=self.root, today=self.day)
        pipeline.move_deal("nj-test", "D001", "Replied", root=self.root, today=self.day)
        pipeline.move_deal("nj-test", "D001", "Call booked", root=self.root, today=self.day)
        pipeline.move_deal("nj-test", "D001", "Lost", reason="has a nephew who builds sites", root=self.root, today=self.day)
        pipeline.move_deal("nj-test", "D002", "Replied", root=self.root, today=self.day)
        f = pipeline.report("nj-test", self.root, today=self.day)
        self.assertEqual([f["funnel_reached"][k] for k in ("Contacted", "Replied", "Call booked")], [3, 2, 1])
        self.assertEqual(f["conversion"]["Replied -> Call booked"], 0.5)
        self.assertEqual(f["lost_reasons"], ["has a nephew who builds sites"])

    def test_capacity_counts_started_projects_and_pauses_outreach(self):
        from leadengine import pipeline
        self.spec_edit(lambda s: s["offer"].update(capacity_per_week=2))
        for i in (1, 2, 3):
            self.won(f"D00{i}", "page1")
            pipeline.record_payment("nj-test", f"D00{i}", 250, root=self.root)
            pipeline.mark_intake("nj-test", f"D00{i}", root=self.root)
        self.assertFalse(pipeline.report("nj-test", self.root, today=self.day)["capacity"]["full"])     # won but not started
        for i in (1, 2):
            pipeline.start_work("nj-test", f"D00{i}", root=self.root, today=self.day)
        self.assertTrue(pipeline.report("nj-test", self.root, today=self.day)["capacity"]["full"])
        self.assertFalse(pipeline.report("nj-test", self.root, today=self.day + dt.timedelta(days=7))["capacity"]["full"])
        write(os.path.join(self.d, "review", "pack-01.csv"), [{"Company": "x", "Lead Key": "x"}], ["Company", "Lead Key"])
        self.assertIn("PAUSE", campaign.status("nj-test", self.root, today=self.day)["next_action"])

    def test_in_person_unlocks_only_at_five_thousand_a_month(self):
        from leadengine import pipeline
        pipeline.add_deal("nj-test", "page1", company="Small Co", monthly=4999, root=self.root, today=self.day)
        pipeline.add_deal("nj-test", "page1", company="Big Co", monthly=5000, root=self.root, today=self.day)
        self.assertEqual(pipeline.report("nj-test", self.root, today=self.day)["in_person_eligible"], ["D002 Big Co"])
        self.assertFalse(pipeline.move_deal("nj-test", "D001", "Replied", root=self.root, today=self.day)[1])
        self.assertTrue(pipeline.move_deal("nj-test", "D002", "Replied", root=self.root, today=self.day)[1])

    def test_in_person_is_not_a_sequence_step(self):
        spec = campaign.load("nj-test", self.root)
        spec["outreach"]["sequence"].append({"day": 20, "channel": "in_person", "action": "Drop by"})
        self.assertTrue(any("in-person" in p for p in campaign.validate(spec)))


class BatchTests(CampaignTests):
    """Reuses CampaignTests' fixtures (sender(), approved(), pack_rows())."""

    def planned(self, n=3, mutate=None):
        self.sender()
        rows, fields = self.pack_rows(n)
        if mutate:
            mutate(rows)
        write(os.path.join(self.d, "approved.csv"), rows, fields)
        out, *_ = campaign.plan_outreach("nj-test", START, self.root)
        return out

    def test_preview_approve_export(self):
        from leadengine import batch
        self.planned(3)
        info = batch.preview("nj-test", "2026-10-12", root=self.root)
        self.assertEqual((info["count"], info["flagged"]), (3, {}))
        text = open(info["path"]).read()
        self.assertIn(info["hash"], text)
        self.assertIn("Practice 0", text)
        with self.assertRaises(SystemExit):
            batch.approve("nj-test", "2026-10-12", "deadbeef0000", root=self.root)       # wrong hash
        self.assertEqual(batch.approve("nj-test", "2026-10-12", info["hash"], root=self.root), (3, 0))
        path, n = batch.export_approved("nj-test", "2026-10-12", root=self.root)
        rows = campaign._read_csv(path)[0]
        self.assertEqual((n, rows[0]["To"]), (3, "doc0@practice0.test"))
        with self.assertRaises(SystemExit):
            batch.preview("nj-test", "2026-10-12", root=self.root)                       # nothing left unapproved

    def test_changed_batch_voids_the_hash(self):
        from leadengine import batch
        out = self.planned(2)
        h = batch.preview("nj-test", "2026-10-12", root=self.root)["hash"]
        rows, fields = campaign._read_csv(out)
        for r in rows:
            if r["Draft"]:
                r["Draft"] += "\nP.S. new line"
        campaign._write_csv(out, rows, fields)
        with self.assertRaises(SystemExit) as cm:
            batch.approve("nj-test", "2026-10-12", h, root=self.root)
        self.assertIn("changed", str(cm.exception))

    def test_flagged_drafts_block_or_are_left_out(self):
        from leadengine import batch

        def bad(rows):
            rows[1]["Draft Email 1"] = "Hi [First name], we noticed {company}.\nReply \"no thanks\" to opt out."
        self.planned(3, bad)
        info = batch.preview("nj-test", "2026-10-12", root=self.root)
        self.assertEqual(len(info["flagged"]), 1)
        with self.assertRaises(SystemExit):
            batch.approve("nj-test", "2026-10-12", info["hash"], root=self.root)
        self.assertEqual(batch.approve("nj-test", "2026-10-12", info["hash"], exclude_flagged=True, root=self.root), (2, 1))
        path, n = batch.export_approved("nj-test", "2026-10-12", root=self.root)
        self.assertNotIn("doc1@practice1.test", open(path).read())

    def test_suppression_added_after_planning_is_caught(self):
        from leadengine import batch
        self.planned(2)
        write(os.path.join(self.d, "suppress.csv"), [{"value": "doc0@practice0.test"}], ["value"])
        info = batch.preview("nj-test", "2026-10-12", root=self.root)
        self.assertTrue(any("suppressed" in " ".join(v) for v in info["flagged"].values()))

    def test_over_cap_blocks(self):
        from leadengine import batch
        self.planned(3)
        spec = campaign.load("nj-test", self.root)
        spec["outreach"]["daily_caps"]["email"] = 1
        with open(os.path.join(self.d, "spec.json"), "w") as fh:
            json.dump(spec, fh)
        info = batch.preview("nj-test", "2026-10-12", root=self.root)
        self.assertTrue(info["over_cap"])
        with self.assertRaises(SystemExit):
            batch.approve("nj-test", "2026-10-12", info["hash"], root=self.root)


if __name__ == "__main__":
    unittest.main()
