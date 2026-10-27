"""Batch email sending: compliance checks, preview and approval, caps and pacing, providers (all mocked), reply sync.
Nothing here sends a real email: providers are fakes, and SMTP and Gmail are exercised through stand-in objects."""
import base64
import csv
import datetime as dt
import email
import io
import json
import os
import smtplib
import tempfile
import unittest
import urllib.error
from zoneinfo import ZoneInfo

from leadengine import batch, campaign, contacts, events, mailer, mailing, replies

NY = ZoneInfo("America/New_York")
TUE = dt.date(2026, 10, 27)
OPEN = dt.datetime(2026, 10, 27, 9, 45, tzinfo=NY)


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def jsave(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def put(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write(path, rows, fields):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


class Clock:
    """A fake clock that only moves when the code sleeps."""

    def __init__(self, start):
        self.t, self.slept = start, []

    def __call__(self):
        return self.t

    def sleep(self, secs):
        self.slept.append(secs)
        self.t += dt.timedelta(seconds=secs)


class FakeProvider:
    name = "fake"

    def __init__(self, account="sam@examplestudio.test", fail=None):
        self.sent, self._account, self.fail, self.closed = [], account, fail or {}, False

    def account(self):
        return self._account

    def send(self, msg):
        exc = self.fail.get(msg["To"])
        if exc:
            raise exc
        self.sent.append(msg)
        return f"id{len(self.sent)}"

    def close(self):
        self.closed = True


FIELDS = ["Company", "Website", "City", "State", "Email", "Email Status", "First Name", "Last Name", "Lead Key", "Decision"]
TEMPLATE = "Subject: A quick idea for {company}\n\nHi {first_name},\n\nI help practices in {city} get a fast website.\n\nWorth a look?\n{sender_name}\n"


class MailBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        campaign.init("nj", "NJ", counties=["Middlesex"], root=self.root)
        self.d = campaign.folder("nj", self.root)
        self.config()
        self.tpl = os.path.join(self.root, "intro.txt")
        with open(self.tpl, "w", encoding="utf-8") as fh:
            fh.write(TEMPLATE)

    def tearDown(self):
        self._tmp.cleanup()

    def config(self, **mail):
        path = os.path.join(self.d, "config.json")
        cfg = jload(path)
        cfg["sender"].update(name="Sam Example", business="Example Studio", address="1 Main St, Edison, NJ 08817", offer="Websites.",
                             reply_email="sam@examplestudio.test")
        cfg["mail"] = {"from_email": "sam@examplestudio.test", "delay_seconds": [60, 180], **mail}
        jsave(path, cfg)

    def contacts(self, n=4, extra=()):
        rows = []
        for i in range(n):
            r = {"Company": f"Practice {i}", "Website": f"https://practice{i}.test", "City": "Edison", "State": "NJ",
                 "Email": f"dr{i}@practice{i}.test", "Email Status": "Risky", "First Name": f"Pat{i}", "Last Name": "Lee", "Decision": "Keep"}
            rows.append(r)
        rows += [dict(r) for r in extra]
        for r in rows:
            r["Lead Key"] = campaign.lead_key(r)
        write(os.path.join(self.d, "approved.csv"), rows, FIELDS)
        return rows

    def planned(self, n=4, **kw):
        self.contacts(n, **kw)
        return mailing.plan("nj", "intro", self.tpl, self.root, today=TUE)

    def approved(self, n=4, batch_no=1):
        self.planned(n)
        h = mailing.preview("nj", "intro", batch_no, self.root, TUE)["hash"]
        mailing.approve("nj", "intro", batch_no, h, self.root, TUE)

    def send(self, prov=None, clock=None, **kw):
        clock = clock or Clock(OPEN)
        prov = prov or FakeProvider()
        res = mailing.send("nj", "intro", kw.pop("batch_no", 1), self.root, prov=prov, clock=clock, sleep=clock.sleep, today=TUE,
                           out=lambda *a: None, **kw)
        return res, prov, clock


class ComplianceTests(MailBase):
    def test_sender_block_must_be_complete(self):
        cfg = mailing.load_cfg("nj", self.root)
        self.assertEqual(mailer.sender_problems(cfg), [])
        cfg["sender"]["address"] = "[Street, City, State ZIP]"
        cfg["mail"]["from_email"] = ""
        cfg["mail"]["unsubscribe_url"] = "http://insecure.test/u"
        probs = " | ".join(mailer.sender_problems(cfg))
        for want in ("sender.address", "postal address", "mail.from_email", "https://"):
            self.assertIn(want, probs)

    def test_subjects_that_mislead_are_refused(self):
        for bad in ("Re: our call", "FWD: plan", "Invoice for Practice 1", "Final notice", "QUICK IDEA FOR YOUR SITE", "Free site!!"):
            self.assertTrue(mailer.subject_problems(bad), bad)
        self.assertEqual(mailer.subject_problems("A quick idea for Practice 1"), [])

    def test_message_headers_and_footer(self):
        cfg = mailing.load_cfg("nj", self.root)
        cfg["mail"]["unsubscribe_email"] = "optout@examplestudio.test"
        foot = mailer.footer(cfg)
        for want in ("1 Main St, Edison, NJ 08817", "marketing email from Example Studio", "no thanks", "optout@examplestudio.test"):
            self.assertIn(want, foot)
        msg = mailer.build(cfg, "dr1@practice1.test", "Hello", "Body\n" + foot)
        self.assertEqual(msg["From"], "Sam Example <sam@examplestudio.test>")
        self.assertIn("mailto:optout@examplestudio.test?subject=unsubscribe", msg["List-Unsubscribe"])
        self.assertIsNone(msg["List-Unsubscribe-Post"])                    # one-click only with a real https endpoint
        cfg["mail"]["unsubscribe_url"] = "https://examplestudio.test/u"
        self.assertEqual(mailer.build(cfg, "a@b.test", "Hi", "x")["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_template_checks(self):
        for bad in ("Hi {first_name}\n", "Subject: Hi {nickname}\n\nBody", "Subject: Hi\n\nHi [First name]"):
            p = os.path.join(self.root, "bad.txt")
            put(p, bad)
            with self.assertRaises(SystemExit):
                mailing.read_template(p)
        s, b, missing = mailing.render(*mailing.read_template(self.tpl), {"Company": "Acme Dental", "City": "", "First Name": ""},
                                       mailing.load_cfg("nj", self.root))
        self.assertEqual((s, missing), ("A quick idea for Acme Dental", ["city"]))
        self.assertTrue(b.startswith("Hi there,"))
        self.assertIn("Sam Example", b)
        self.assertIn("1 Main St", b)


class PlanPreviewApproveTests(MailBase):
    def test_who_is_left_out(self):
        extra = [
            {"Company": "Opted Out", "Website": "https://optout.test", "City": "Edison", "Email": "x@optout.test", "Email Status": "Valid"},
            {"Company": "Replied", "Website": "https://replied.test", "City": "Edison", "Email": "y@replied.test", "Email Status": "Valid"},
            {"Company": "Unchecked", "Website": "https://unchecked.test", "City": "Edison", "Email": "z@unchecked.test", "Email Status": "Unverified"},
            {"Company": "Practice 0 again", "Website": "https://other.test", "City": "Edison", "Email": "dr0@practice0.test", "Email Status": "Valid"},
            {"Company": "Same Domain", "Website": "https://practice1.test/b", "City": "Edison", "Email": "office@practice1.test", "Email Status": "Valid"},
            {"Company": "No City", "Website": "https://nocity.test", "City": "", "Email": "a@nocity.test", "Email Status": "Valid"},
            {"Company": "Gmail One", "Website": "", "City": "Edison", "Email": "one.practice@gmail.com", "Email Status": "Valid"},
            {"Company": "Gmail Two", "Website": "", "City": "Edison", "Email": "two.practice@gmail.com", "Email Status": "Valid"},
            {"Company": "No Email", "Website": "https://noemail.test", "City": "Edison", "Email": "", "Email Status": ""},
        ]
        write(os.path.join(self.d, "suppress.csv"), [{"value": "x@optout.test"}], ["value"])
        write(os.path.join(self.d, "events.csv"), [{"Date": "2026-10-20", "Lead Key": "", "Company": "Replied", "Email": "y@replied.test",
                                                    "Event": "Replied", "Points": 20, "Notes": "", "Imported": "2026-10-20"}], events.FIELDS)
        r = self.planned(4, extra=extra)
        recips = campaign._read_csv(os.path.join(mailing.mail_dir("nj", "intro", self.root), "recipients.csv"))[0]
        self.assertEqual(sorted(x["Email"] for x in recips),
                         ["dr0@practice0.test", "dr1@practice1.test", "dr2@practice2.test", "dr3@practice3.test",
                          "one.practice@gmail.com", "two.practice@gmail.com"])        # free mail is not grouped by domain
        out = {x["Company"]: x["Reason"] for x in campaign._read_csv(os.path.join(mailing.mail_dir("nj", "intro", self.root), "excluded.csv"))[0]}
        self.assertIn("suppressed", out["Opted Out"])
        self.assertIn("replied", out["Replied"])
        self.assertIn("Unverified", out["Unchecked"])
        self.assertIn("earlier in the list", out["Practice 0 again"])
        self.assertIn("practice1.test", out["Same Domain"])
        self.assertIn("city", out["No City"])
        self.assertIn("no valid email", out["No Email"])
        self.assertEqual(r["recipients"], 6)

    def test_batches_preview_and_hash(self):
        self.config(batch_size=3)
        r = self.planned(7)
        self.assertEqual((r["batches"], r["batch_size"]), (3, 3))
        info = mailing.preview("nj", "intro", 2, self.root, TUE)
        with open(info["path"], encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(info["count"], 3)
        for want in (info["hash"], "From: Sam Example <sam@examplestudio.test>", "List-Unsubscribe", "Hi Pat3,", "1 Main St, Edison",
                     "Nothing is sent by this preview", "Practice 5 <dr5@practice5.test>"):
            self.assertIn(want, text)
        with self.assertRaises(SystemExit):
            mailing.approve("nj", "intro", 2, "000000000000", self.root, TUE)
        self.assertEqual(mailing.approve("nj", "intro", 2, info["hash"], self.root, TUE), 3)
        with self.assertRaises(SystemExit):
            mailing.plan("nj", "intro", self.tpl, self.root, today=TUE)                 # ids are not reused

    def test_unapproved_batch_cannot_send(self):
        self.planned(2)
        with self.assertRaises(SystemExit) as cm:
            self.send()
        self.assertIn("not approved", str(cm.exception))

    def test_plan_refuses_an_incomplete_sender(self):
        cfg = jload(os.path.join(self.d, "config.json"))
        cfg["sender"]["address"] = "[Street, City, State ZIP]"
        jsave(os.path.join(self.d, "config.json"), cfg)
        self.contacts(2)
        with self.assertRaises(SystemExit) as cm:
            mailing.plan("nj", "intro", self.tpl, self.root, today=TUE)
        self.assertIn("postal address", str(cm.exception))


class SendTests(MailBase):
    def test_sends_paced_logged_and_once(self):
        self.approved(3)
        res, prov, clock = self.send()
        self.assertEqual((res["sent"], res["stopped"]), (3, ""))
        self.assertEqual(len(clock.slept), 2)                                # a pause between emails, not before the first
        self.assertTrue(all(60 <= s <= 180 for s in clock.slept))
        msg = prov.sent[0]
        self.assertEqual(msg["To"], "dr0@practice0.test")
        self.assertIn("Hi Pat0,", msg.get_content())
        self.assertIn("1 Main St, Edison, NJ 08817", msg.get_content())
        self.assertTrue(prov.closed)
        led = mailer.read_ledger(self.root)
        self.assertEqual([r["Status"] for r in led], ["sent"] * 3)
        self.assertEqual(led[0]["Mailing"], "intro")
        ev = campaign._read_csv(os.path.join(self.d, "events.csv"))[0]
        self.assertEqual([e["Event"] for e in ev], ["Email sent"] * 3)
        with self.assertRaises(SystemExit):                                  # all sent: nothing left
            self.send()

    def test_opt_out_after_approval_is_skipped(self):
        self.approved(3)
        write(os.path.join(self.d, "suppress.csv"), [{"value": "dr1@practice1.test"}], ["value"])
        res, prov, _ = self.send()
        self.assertEqual((res["sent"], [m["To"] for m in prov.sent]), (2, ["dr0@practice0.test", "dr2@practice2.test"]))

    def test_changed_content_is_not_sent(self):
        self.approved(2)
        cfg = jload(os.path.join(self.d, "config.json"))
        cfg["sender"]["name"] = "Someone Else"
        jsave(os.path.join(self.d, "config.json"), cfg)
        with self.assertRaises(SystemExit) as cm:
            self.send()
        self.assertIn("changed since approval", str(cm.exception))

    def test_send_window(self):
        self.approved(2)
        night = Clock(dt.datetime(2026, 10, 27, 23, 0, tzinfo=NY))
        res, prov, _ = self.send(clock=night)
        self.assertEqual(res["sent"], 0)
        self.assertIn("Wed 2026-10-28 09:30", res["stopped"])
        res, prov, clock = self.send(clock=night, wait=True)
        self.assertEqual(res["sent"], 2)
        self.assertEqual(clock.t.date(), dt.date(2026, 10, 28))
        fri = Clock(dt.datetime(2026, 10, 30, 12, 0, tzinfo=NY))              # after Friday's window: the next one is Monday
        self.assertEqual(mailer.window(campaign.load("nj", self.root), fri.t)[1].date(), dt.date(2026, 11, 2))

    def test_window_closing_mid_batch_stops(self):
        self.config(delay_seconds=[3600, 3600])
        self.approved(3)
        res, _, _ = self.send(clock=Clock(dt.datetime(2026, 10, 27, 10, 0, tzinfo=NY)))
        self.assertEqual(res["sent"], 2)
        self.assertIn("window closed", res["stopped"])

    def test_warmup_cap(self):
        self.config(batch_size=12, delay_seconds=[5, 5])
        self.approved(12)
        self.assertEqual(mailer.cap_today(self.root, mailing.load_cfg("nj", self.root), TUE), (10, 0))   # a new address: week 1
        res, prov, _ = self.send(clock=Clock(dt.datetime(2026, 10, 27, 9, 30, tzinfo=NY)))
        self.assertEqual(res["sent"], 10)
        self.assertIn("cap of 10", res["stopped"])
        cfg = mailing.load_cfg("nj", self.root)
        self.assertEqual(mailer.cap_today(self.root, cfg, TUE + dt.timedelta(days=8)), (20, 0))
        self.assertEqual(mailer.cap_today(self.root, cfg, TUE + dt.timedelta(days=15)), (30, 0))

    def test_bounce_suppresses_and_failures_stop(self):
        self.approved(5)
        prov = FakeProvider(fail={"dr0@practice0.test": mailer.Permanent("550 no such user"),
                                  "dr1@practice1.test": mailer.Temporary("421 busy"),
                                  "dr2@practice2.test": mailer.Permanent("550 gone")})
        res, prov, _ = self.send(prov=prov)
        self.assertEqual((res["sent"], res["failed"], res["bounced"]), (0, 3, 2))
        self.assertIn("3 failures", res["stopped"])
        sup = campaign.load_suppressions("nj", self.root)
        self.assertTrue({"dr0@practice0.test", "dr2@practice2.test"} <= sup)
        self.assertNotIn("dr1@practice1.test", sup)                          # a temporary failure is retried next run

    def test_fatal_error_stops_at_once(self):
        self.approved(3)
        prov = FakeProvider(fail={"dr0@practice0.test": mailer.Fatal("login refused")})
        res, prov, _ = self.send(prov=prov)
        self.assertEqual((res["sent"], res["stopped"]), (0, "login refused"))

    def test_dry_run_writes_files_and_counts_nothing(self):
        self.approved(2)
        res = mailing.send("nj", "intro", 1, self.root, dry_run=True, today=TUE, out=lambda *a: None)
        files = sorted(os.listdir(res["outbox"]))
        self.assertEqual(len(files), 2)
        with open(os.path.join(res["outbox"], files[0]), "rb") as fh:
            msg = email.message_from_bytes(fh.read())
        self.assertEqual(msg["Subject"], "A quick idea for Practice 0")
        self.assertEqual({r["Status"] for r in mailer.read_ledger(self.root)}, {"dry-run"})
        self.assertFalse(os.path.exists(os.path.join(self.d, "events.csv")))
        res, prov, _ = self.send()                                           # the real send still goes to both
        self.assertEqual(res["sent"], 2)

    def test_recent_email_blocks_a_second_mailing(self):
        self.approved(2)
        self.send()
        put(self.tpl, TEMPLATE.replace("A quick idea", "Another idea"))
        r = mailing.plan("nj", "second", self.tpl, self.root, today=TUE + dt.timedelta(days=5))
        self.assertEqual(r["recipients"], 0)
        self.assertIn("emailed on DATE", " ".join(r["reasons"]))

    def test_high_bounce_rate_blocks_sending(self):
        rows = [{"Date": "2026-10-20", "Lead Key": f"k{i}", "Company": "", "Email": f"e{i}@x.test", "Event": "Email sent", "Points": 0,
                 "Notes": "", "Imported": ""} for i in range(20)]
        rows += [{**rows[i], "Event": "Bounced"} for i in range(3)]
        self.approved(2)
        write(os.path.join(self.d, "events.csv"), rows, events.FIELDS)      # bounces reported after approval still stop the send
        res, prov, _ = self.send()
        self.assertEqual(res["sent"], 0)
        self.assertIn("bounced", res["stopped"])

    def test_test_send_only_to_own_address(self):
        self.planned(2)
        with self.assertRaises(SystemExit):
            mailing.test_send("nj", "intro", "dr0@practice0.test", self.root, prov=FakeProvider())
        prov = FakeProvider()
        mailing.test_send("nj", "intro", "sam@examplestudio.test", self.root, prov=prov)
        self.assertEqual(prov.sent[0]["Subject"], "[TEST] A quick idea for Practice 0")
        self.assertEqual(mailer.read_ledger(self.root), [])

    def test_status(self):
        self.config(batch_size=2)
        self.approved(3)
        self.send()
        st = mailing.status("nj", self.root, today=TUE)
        self.assertEqual(st["sent_today"], 2)
        self.assertEqual(st["mailings"]["intro"]["batches"][1]["sent"], 2)
        self.assertFalse(st["mailings"]["intro"]["batches"][2]["approved"])


class SequenceSendTests(MailBase):
    def planned_tasks(self, body=None):
        cfg = jload(os.path.join(self.d, "config.json"))
        cfg["sender"]["offer"] = "We build websites."
        jsave(os.path.join(self.d, "config.json"), cfg)
        rows = self.contacts(2)
        fields = FIELDS + ["Draft Subject", "Draft Email 1", "Phone", "LinkedIn URL"]
        for r in rows:
            r["Draft Subject"] = f"Idea for {r['Company']}"
            r["Draft Email 1"] = body or 'Hi.\n\nSam Example\nExample Studio · 1 Main St, Edison, NJ 08817\nReply "no thanks" and I won\'t write again.'
        write(os.path.join(self.d, "approved.csv"), rows, fields)
        campaign.plan_outreach("nj", TUE, self.root)
        h = batch.preview("nj", TUE.isoformat(), root=self.root)["hash"]
        batch.approve("nj", TUE.isoformat(), h, root=self.root)

    def test_sends_and_marks_done(self):
        self.planned_tasks()
        clock = Clock(OPEN)
        prov = FakeProvider()
        res = batch.send("nj", TUE.isoformat(), root=self.root, prov=prov, clock=clock, sleep=clock.sleep, today=TUE, out=lambda *a: None)
        self.assertEqual(res["sent"], 2)
        self.assertTrue(prov.sent[0]["List-Unsubscribe"])
        tasks = [t for f in batch._files("nj", self.root) for t in campaign._read_csv(f)[0] if t["Draft"]]
        self.assertEqual({t["Done (Y/N)"] for t in tasks}, {"Y"})
        with self.assertRaises(SystemExit):
            batch.send("nj", TUE.isoformat(), root=self.root, prov=prov, clock=clock, sleep=clock.sleep, today=TUE)

    def test_draft_without_address_is_refused(self):
        self.planned_tasks(body='Hi.\nReply "no thanks" to opt out.')
        with self.assertRaises(SystemExit) as cm:
            batch.send("nj", TUE.isoformat(), root=self.root, prov=FakeProvider(), today=TUE)
        self.assertIn("postal address", str(cm.exception))


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None, context=None):
        self.calls, self.host, self.port = [], host, port
        FakeSMTP.instances.append(self)

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, pw):
        if pw == "wrong":
            raise smtplib.SMTPAuthenticationError(535, b"bad")
        self.calls.append(("login", user))

    def send_message(self, msg):
        if msg["To"] == "gone@x.test":
            raise smtplib.SMTPRecipientsRefused({"gone@x.test": (550, b"no such user")})
        self.calls.append(("send", msg["To"]))
        return {}

    def quit(self):
        self.calls.append("quit")


class FakeHTTP:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return io.BytesIO(json.dumps(r).encode())


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cdir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def msg(self, to="dr@practice.test"):
        m = email.message.EmailMessage()
        m["From"], m["To"], m["Subject"], m["Message-ID"] = "sam@examplestudio.test", to, "Hi", "<1@examplestudio.test>"
        m.set_content("Hello")
        return m

    def test_smtp(self):
        p = mailer.SMTPProvider({"host": "smtp.test", "port": 587, "user": "sam@examplestudio.test", "password": "app", "security": "starttls"},
                                smtp=FakeSMTP)
        self.assertEqual(p.send(self.msg()), "<1@examplestudio.test>")
        with self.assertRaises(mailer.Permanent):
            p.send(self.msg("gone@x.test"))
        conn = FakeSMTP.instances[-1]
        p.close()
        self.assertEqual(conn.calls[:4], ["ehlo", "starttls", "ehlo", ("login", "sam@examplestudio.test")])
        self.assertEqual(conn.calls[-1], "quit")
        bad = mailer.SMTPProvider({"host": "smtp.test", "port": 587, "user": "u", "password": "wrong", "security": "starttls"}, smtp=FakeSMTP)
        with self.assertRaises(mailer.Fatal):
            bad.send(self.msg())

    def test_smtp_settings_from_env_or_missing(self):
        old = {k: os.environ.pop(k, None) for k in list(os.environ) if k.startswith("LEADENGINE_")}
        try:
            os.environ["LEADENGINE_CONFIG_DIR"] = self.cdir
            with self.assertRaises(mailer.SetupError):
                mailer.smtp_settings()
            os.environ.update(LEADENGINE_SMTP_HOST="smtp.gmail.com", LEADENGINE_SMTP_USER="sam@examplestudio.test", LEADENGINE_SMTP_PASSWORD="x")
            s = mailer.smtp_settings()
            self.assertEqual((s["port"], s["security"]), (587, "starttls"))
        finally:
            for k in [k for k in os.environ if k.startswith("LEADENGINE_")]:
                del os.environ[k]
            os.environ.update({k: v for k, v in old.items() if v is not None})

    def gmail(self, responses):
        jsave(os.path.join(self.cdir, "gmail-client.json"), {"installed": {"client_id": "cid", "client_secret": "sec"}})
        jsave(os.path.join(self.cdir, "gmail-token.json"), {"refresh_token": "rt"})
        http = FakeHTTP(responses)
        return mailer.GmailProvider(self.cdir, opener=http), http

    def test_gmail_send_and_errors(self):
        g, http = self.gmail([{"access_token": "at"}, {"emailAddress": "sam@examplestudio.test"}, {"id": "abc"},
                              urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b"Invalid To header")),
                              urllib.error.HTTPError("u", 429, "slow", {}, io.BytesIO(b"rateLimitExceeded"))])
        self.assertEqual(g.account(), "sam@examplestudio.test")
        self.assertEqual(g.send(self.msg()), "abc")
        raw = json.loads(http.requests[2].data)["raw"]
        self.assertEqual(email.message_from_bytes(base64.urlsafe_b64decode(raw))["To"], "dr@practice.test")
        self.assertEqual(http.requests[2].get_header("Authorization"), "Bearer at")
        with self.assertRaises(mailer.Permanent):
            g.send(self.msg())
        with self.assertRaises(mailer.Fatal):
            g.send(self.msg())

    def test_gmail_from_must_match(self):
        g, _ = self.gmail([{"access_token": "at"}, {"emailAddress": "other@gmail.com"}])
        with self.assertRaises(mailer.SetupError):
            mailer.check_account(g, {"mail": {"from_email": "sam@examplestudio.test"}})

    def test_gmail_not_set_up(self):
        with self.assertRaises(mailer.SetupError):
            mailer.GmailProvider(self.cdir)

    def test_providers_are_pluggable(self):
        mailer.register("ses-test", lambda **kw: FakeProvider())
        try:
            self.assertEqual(mailer.provider("ses-test", self.cdir, {"mail": {"from_email": "a@b.test"}}).name, "fake")
            with self.assertRaises(mailer.SetupError):
                mailer.provider("pigeon", self.cdir, {"mail": {"from_email": "a@b.test"}})
        finally:
            del mailer.PROVIDERS["ses-test"]


class ReplySyncTests(MailBase):
    def test_replies_opt_outs_bounces(self):
        self.approved(4)
        self.send()

        class Reader:
            def search(self, senders, since):
                return [
                    {"from": "dr0@practice0.test", "subject": "Re: A quick idea", "date": "Wed, 28 Oct 2026 10:00:00 -0400", "snippet": "No thanks, please remove me", "failed": ""},
                    {"from": "dr1@practice1.test", "subject": "Re: A quick idea", "date": "Wed, 28 Oct 2026 11:00:00 -0400", "snippet": "Sounds good, call me", "failed": ""},
                    {"from": "dr3@practice3.test", "subject": "Automatic reply: out of office", "date": "Wed, 28 Oct 2026 11:00:00 -0400", "snippet": "", "failed": ""},
                    {"from": "mailer-daemon@googlemail.com", "subject": "Delivery Status Notification (Failure)", "date": "Tue, 27 Oct 2026 10:05:00 -0400",
                     "snippet": "Your message wasn't delivered to dr2@practice2.test because the address couldn't be found", "failed": ""},
                    {"from": "stranger@else.test", "subject": "Hello", "date": "", "snippet": "", "failed": ""},
                ]

        res = replies.sync("nj", self.root, reader=Reader(), today=dt.date(2026, 10, 28))
        self.assertEqual(res["events"], 3)
        sup = campaign.load_suppressions("nj", self.root)
        self.assertIn("dr0@practice0.test", sup)                             # "no thanks" is an opt-out
        self.assertIn("dr2@practice2.test", sup)                             # bounced
        self.assertNotIn("dr1@practice1.test", sup)
        ev = {(e["Email"], e["Event"]) for e in campaign._read_csv(os.path.join(self.d, "events.csv"))[0]}
        self.assertIn(("dr1@practice1.test", "Replied"), ev)
        self.assertNotIn(("dr3@practice3.test", "Replied"), ev)              # an auto-reply is not an answer
        ctx = mailing.context("nj", self.root, mailing.load_cfg("nj", self.root), "next", dt.date(2026, 12, 15))
        row = {"Email": "dr1@practice1.test", "Lead Key": "practice1.test", "Company": "Practice 1", "Email Status": "Risky"}
        self.assertIn("replied", mailing.blocked(row, ctx, mailing.load_cfg("nj", self.root)))   # a reply stops future mailings too

    def test_gmail_queries_are_chunked(self):
        qs = replies._gmail_query({f"a{i}@x.test" for i in range(45)}, TUE)
        self.assertEqual(len(qs), 4)
        self.assertTrue(qs[-1].startswith("from:(mailer-daemon OR postmaster) after:2026/10/27"))


class NoHarvestTests(unittest.TestCase):
    def test_site_notice_keeps_addresses_out(self):
        html = '<a href="mailto:info@shop.test">Email</a><p>We will not sell or share any e-mail address listed on this site.</p>'
        self.assertTrue(contacts.extract(html, "https://shop.test")["no_harvest"])
        self.assertFalse(contacts.extract('<a href="mailto:info@shop.test">x</a>', "https://shop.test")["no_harvest"])
        with tempfile.TemporaryDirectory() as d:
            f = contacts.ContactFinder(d, fetcher=lambda url: (url, "" if url.endswith("robots.txt") else html), sleep=lambda s: None)
            got = f.find("https://shop.test")
        self.assertEqual(got["email"], "")
        self.assertIn("none kept", got["note"])


class CLITests(MailBase):
    def test_send_needs_a_person(self):
        self.approved(1)
        import sys
        old = sys.stdin
        sys.stdin = io.StringIO("")
        try:
            with self.assertRaises(SystemExit) as cm:
                campaign.main(["--root", self.root, "mail", "send", "nj", "intro", "--batch", "1"])
            self.assertIn("person at the keyboard", str(cm.exception))
            with self.assertRaises(SystemExit) as cm:
                campaign.main(["--root", self.root, "batch", "send", "nj", TUE.isoformat()])
            self.assertIn("person at the keyboard", str(cm.exception))
        finally:
            sys.stdin = old
        self.assertEqual(mailer.read_ledger(self.root), [])


if __name__ == "__main__":
    unittest.main()
