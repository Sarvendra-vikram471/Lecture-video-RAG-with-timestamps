const input = document.getElementById("api");
const msg = document.getElementById("msg");

chrome.storage.sync.get("apiBase").then(({ apiBase }) => (input.value = apiBase || "http://localhost:8000"));

document.getElementById("save").onclick = async () => {
  const url = input.value.trim().replace(/\/+$/, "");
  // a non-localhost backend needs host permission, requested at save time
  if (!/^http:\/\/(localhost|127\.0\.0\.1)/.test(url)) {
    const granted = await chrome.permissions.request({ origins: [new URL(url).origin + "/*"] });
    if (!granted) return (msg.textContent = "Permission denied for that URL.");
  }
  await chrome.storage.sync.set({ apiBase: url });
  msg.textContent = "Saved. Reload the YouTube tab.";
};

document.getElementById("test").onclick = () => {
  msg.textContent = "Testing...";
  chrome.runtime.sendMessage({ type: "api", path: "/health" }, (r) => {
    msg.textContent = r && r.ok ? "✅ Backend reachable" : "❌ " + ((r && r.data.detail) || "Not reachable");
  });
};
