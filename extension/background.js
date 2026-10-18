// All backend calls go through here: pages on youtube.com may not call localhost
// directly (Chrome's private-network rules), but the extension's worker can.
const DEFAULT_API = "http://localhost:8000";

async function apiBase() {
  const { apiBase } = await chrome.storage.sync.get("apiBase");
  return (apiBase || DEFAULT_API).replace(/\/+$/, "");
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "api") return;
  (async () => {
    try {
      const res = await fetch((await apiBase()) + msg.path, {
        method: msg.method || "GET",
        headers: { "Content-Type": "application/json" },
        body: msg.body ? JSON.stringify(msg.body) : undefined,
      });
      const data = await res.json().catch(() => ({}));
      sendResponse({ ok: res.ok, status: res.status, data });
    } catch (e) {
      sendResponse({ ok: false, status: 0, data: { detail: "Backend not reachable: " + e.message } });
    }
  })();
  return true; // keep the channel open for the async response
});
