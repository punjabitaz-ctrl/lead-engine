// Pure helpers for the lead-tracker edge function. No Deno APIs here so Node can test them.

export const KEY_PAGES = /^\/(projects|portfolio|contact|pricing|book)(\/|$)/i;

const BOT_UA = /bot|spider|crawl|preview|scanner|proofpoint|mimecast|barracuda|trendmicro|symantec|messagelabs|forcepoint|fireeye|googleimageproxy|microsoft office|python-requests|curl\/|wget|headless|go-http-client|java\//i;

export function isBot(ua: string | null | undefined): boolean {
  return !ua || BOT_UA.test(ua);
}

export function validLeadKey(k: string | null | undefined): k is string {
  return typeof k === "string" && k.length >= 1 && k.length <= 200 && !/[\u0000-\u001f]/.test(k);
}

/** https only, host must equal an allowed host or be a subdomain of one. Blocks open-redirect abuse. */
export function allowedTarget(to: string | null | undefined, allowedHosts: string[]): URL | null {
  if (!to) return null;
  let u: URL;
  try {
    u = new URL(to);
  } catch {
    return null;
  }
  if (u.protocol !== "https:" || u.username || u.password) return null;
  const host = u.hostname.toLowerCase();
  const ok = allowedHosts.some((h) => {
    const a = h.trim().toLowerCase();
    return a !== "" && (host === a || host.endsWith("." + a));
  });
  return ok ? u : null;
}

export function redirectUrl(target: URL, leadKey: string): string {
  const u = new URL(target.toString());
  if (!u.searchParams.has("utm_source")) u.searchParams.set("utm_source", "leadengine");
  if (!u.searchParams.has("utm_medium")) u.searchParams.set("utm_medium", "email");
  if (!u.searchParams.has("utm_content")) u.searchParams.set("utm_content", leadKey);
  return u.toString();
}

/** Raw event -> the names used on the sheet's Events tab (Config rows 96-106). */
export function sheetEventName(event: string, path: string | null | undefined): string | null {
  if (event === "link_click") return "Email link clicked";
  if (event === "form_submit") return "Form submitted";
  if (event === "page_view") return KEY_PAGES.test(path ?? "") ? "Key page visit (portfolio / pricing / contact)" : "Website visit";
  return null;
}

export interface RawEvent { ts: string; lead_key: string; event: string; path: string | null }
export interface SheetEvent { ts: string; lead_key: string; event: string }

/** One row per lead + event name + UTC day, so repeat clicks and reloads do not inflate the score. */
export function toSheetEvents(rows: RawEvent[]): SheetEvent[] {
  const seen = new Set<string>();
  const out: SheetEvent[] = [];
  for (const r of rows) {
    const name = sheetEventName(r.event, r.path);
    if (!name) continue;
    const k = `${r.lead_key}\u0000${name}\u0000${r.ts.slice(0, 10)}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push({ ts: r.ts, lead_key: r.lead_key, event: name });
  }
  return out;
}

export function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function originAllowed(origin: string | null, allowedHosts: string[]): boolean {
  if (!origin) return false;
  try {
    const u = new URL(origin);
    return allowedTarget(`https://${u.hostname}/`, allowedHosts) !== null;
  } catch {
    return false;
  }
}
