// Supabase Edge Function: lead-tracker. Deploy with verify_jwt = false (recipients have no Supabase login).
//   GET  /t?l=<lead key>&to=<https url>   log a click, then 302 to the target (allow-listed hosts only)
//   POST /e  {l, e: page_view|form_submit, p}   beacon from your own sites (allow-listed origins only)
//   GET  /export?since=<iso>              events for the sheet; header x-export-token must match EXPORT_TOKEN
// Secrets: ALLOWED_HOSTS (comma list, e.g. tazabbas.com,momento.family), EXPORT_TOKEN.
// SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are provided by Supabase.
import {
  allowedTarget, constantTimeEqual, isBot, originAllowed, redirectUrl, toSheetEvents, validLeadKey,
} from "./lib.ts";

const URL_ = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const HOSTS = (Deno.env.get("ALLOWED_HOSTS") ?? "").split(",").map((h) => h.trim()).filter(Boolean);
const EXPORT_TOKEN = Deno.env.get("EXPORT_TOKEN") ?? "";
const REST = `${URL_}/rest/v1/lead_events`;
const H = { apikey: KEY, Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" };

async function log(row: Record<string, unknown>) {
  try {
    await fetch(REST, { method: "POST", headers: { ...H, Prefer: "return=minimal" }, body: JSON.stringify(row) });
  } catch (_) { /* never block the visitor on logging */ }
}

Deno.serve(async (req) => {
  const { pathname, searchParams } = new URL(req.url);
  const ua = (req.headers.get("user-agent") ?? "").slice(0, 300);

  if (req.method === "GET" && pathname.endsWith("/t")) {
    const lead = searchParams.get("l");
    const target = allowedTarget(searchParams.get("to"), HOSTS);
    if (!target || !validLeadKey(lead)) return new Response("Bad link", { status: 400 });
    await log({ lead_key: lead, event: "link_click", target: target.origin + target.pathname, is_bot: isBot(ua), ua });
    return new Response(null, { status: 302, headers: { Location: redirectUrl(target, lead), "Cache-Control": "no-store" } });
  }

  if (pathname.endsWith("/e")) {
    const origin = req.headers.get("origin");
    const cors = { "Access-Control-Allow-Origin": origin ?? "", "Vary": "Origin" };
    if (req.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: { ...cors, "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "content-type" } });
    }
    if (req.method !== "POST" || !originAllowed(origin, HOSTS)) return new Response("Forbidden", { status: 403 });
    let b: { l?: string; e?: string; p?: string } = {};
    try { b = JSON.parse(await req.text()); } catch (_) { return new Response("Bad request", { status: 400, headers: cors }); }
    if (!validLeadKey(b.l) || !["page_view", "form_submit"].includes(b.e ?? "")) return new Response("Bad request", { status: 400, headers: cors });
    await log({ lead_key: b.l, event: b.e, path: (b.p ?? "").slice(0, 300), is_bot: isBot(ua), ua });
    return new Response(null, { status: 204, headers: cors });
  }

  if (req.method === "GET" && pathname.endsWith("/export")) {
    const token = req.headers.get("x-export-token") ?? "";
    if (!EXPORT_TOKEN || !constantTimeEqual(token, EXPORT_TOKEN)) return new Response("Forbidden", { status: 403 });
    const since = searchParams.get("since") ?? "1970-01-01T00:00:00Z";
    const q = `${REST}?select=ts,lead_key,event,path&is_bot=eq.false&ts=gt.${encodeURIComponent(since)}&order=ts.asc&limit=1000`;
    const res = await fetch(q, { headers: H });
    if (!res.ok) return new Response("Upstream error", { status: 502 });
    const rows = await res.json();
    const events = toSheetEvents(rows);
    const next = rows.length ? rows[rows.length - 1].ts : since;
    return new Response(JSON.stringify({ events, next_since: next, more: rows.length === 1000 }), {
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  }

  return new Response("Not found", { status: 404 });
});
