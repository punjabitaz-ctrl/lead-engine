import test from "node:test";
import assert from "node:assert/strict";
import {
  allowedTarget, constantTimeEqual, isBot, originAllowed, redirectUrl, sheetEventName, toSheetEvents, validLeadKey,
} from "./lib.ts";

const HOSTS = ["tazabbas.com", "momento.family"];

test("allowedTarget blocks open-redirect tricks", () => {
  assert.ok(allowedTarget("https://tazabbas.com/projects", HOSTS));
  assert.ok(allowedTarget("https://www.tazabbas.com/projects", HOSTS));
  for (const bad of ["https://evil.com/", "http://tazabbas.com/", "https://tazabbas.com.evil.com/", "https://tazabbas.com@evil.com/",
                     "javascript:alert(1)", "//evil.com", "", null, "not a url", "https://eviltazabbas.com/"]) {
    assert.equal(allowedTarget(bad as string, HOSTS), null, String(bad));
  }
});

test("redirectUrl adds utm once and keeps existing", () => {
  const u = redirectUrl(new URL("https://tazabbas.com/projects?utm_medium=x"), "garden state|newark");
  const p = new URL(u).searchParams;
  assert.equal(p.get("utm_source"), "leadengine");
  assert.equal(p.get("utm_medium"), "x");
  assert.equal(p.get("utm_content"), "garden state|newark");
});

test("bot detection", () => {
  assert.ok(isBot(""));
  assert.ok(isBot("Mozilla/5.0 (compatible; Proofpoint URL Defense)"));
  assert.ok(isBot("python-requests/2.31"));
  assert.ok(!isBot("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"));
});

test("lead key validation", () => {
  assert.ok(validLeadKey("earthcam.net"));
  assert.ok(!validLeadKey(""));
  assert.ok(!validLeadKey("a".repeat(201)));
  assert.ok(!validLeadKey("bad\nkey"));
  assert.ok(!validLeadKey(null));
});

test("sheet event names match Config rows", () => {
  assert.equal(sheetEventName("link_click", null), "Email link clicked");
  assert.equal(sheetEventName("form_submit", "/x"), "Form submitted");
  assert.equal(sheetEventName("page_view", "/projects/ayin"), "Key page visit (portfolio / pricing / contact)");
  assert.equal(sheetEventName("page_view", "/blog"), "Website visit");
  assert.equal(sheetEventName("nope", "/"), null);
});

test("export dedupes per lead, event and day", () => {
  const rows = [
    { ts: "2026-10-09T10:00:00Z", lead_key: "a.com", event: "link_click", path: null },
    { ts: "2026-10-09T11:00:00Z", lead_key: "a.com", event: "link_click", path: null },
    { ts: "2026-10-10T09:00:00Z", lead_key: "a.com", event: "link_click", path: null },
    { ts: "2026-10-09T12:00:00Z", lead_key: "a.com", event: "page_view", path: "/contact" },
    { ts: "2026-10-09T12:05:00Z", lead_key: "b.com", event: "link_click", path: null },
  ];
  assert.equal(toSheetEvents(rows).length, 4);
});

test("constant time compare and origin check", () => {
  assert.ok(constantTimeEqual("abc", "abc"));
  assert.ok(!constantTimeEqual("abc", "abd"));
  assert.ok(!constantTimeEqual("abc", "ab"));
  assert.ok(originAllowed("https://tazabbas.com", HOSTS));
  assert.ok(!originAllowed("https://evil.com", HOSTS));
  assert.ok(!originAllowed(null, HOSTS));
});
