/* Paste before </body> on your own sites. Fires only for visitors who arrived through a tracked lead-engine link
   (utm_source=leadengine). Stores one value (the lead key) in sessionStorage. Disclose this in your privacy policy. */
(function () {
  var ENDPOINT = "https://YOUR-PROJECT.supabase.co/functions/v1/lead-tracker/e";
  var q = new URLSearchParams(location.search), k = null;
  try {
    if (q.get("utm_source") === "leadengine" && q.get("utm_content")) sessionStorage.setItem("le_key", q.get("utm_content"));
    k = sessionStorage.getItem("le_key");
  } catch (e) { k = q.get("utm_source") === "leadengine" ? q.get("utm_content") : null; }
  if (!k) return;
  function send(ev) {
    var body = JSON.stringify({ l: k, e: ev, p: location.pathname });
    if (navigator.sendBeacon) navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "text/plain" }));
    else fetch(ENDPOINT, { method: "POST", body: body, keepalive: true, mode: "no-cors" });
  }
  send("page_view");
  document.addEventListener("submit", function () { send("form_submit"); }, true);
})();
