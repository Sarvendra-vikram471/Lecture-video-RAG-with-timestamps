// Injects the Lecture RAG panel next to the YouTube player.
(() => {
  const PANEL_ID = "lrag-panel";
  let currentVideo = null;
  let chapters = [];
  let pollTimer = null;

  // ---------- helpers ----------
  const api = (path, method = "GET", body) =>
    new Promise((resolve) => chrome.runtime.sendMessage({ type: "api", path, method, body }, resolve));

  const videoId = () => new URLSearchParams(location.search).get("v");
  const player = () => document.querySelector("video.html5-main-video") || document.querySelector("video");

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const toSeconds = (t) => t.split(":").reduce((acc, p) => acc * 60 + Number(p), 0);

  function jump(seconds) {
    const v = player();
    if (!v) return;
    v.currentTime = seconds;
    v.play();
  }

  // Turn "14:32" / "1:02:03" inside answer text into clickable jump links.
  const linkTimestamps = (html) =>
    html.replace(/\b(\d{1,2}:)?\d{1,2}:\d{2}\b/g, (t) => `<a class="lrag-ts" data-t="${toSeconds(t)}">${t}</a>`);

  // Parse the JSON array that follows `key` in html, matching brackets (arrays nest inside).
  function extractJsonArray(html, key) {
    const at = html.indexOf(key);
    if (at < 0) return null;
    const start = html.indexOf("[", at);
    let depth = 0, inStr = false;
    for (let i = start; i < html.length; i++) {
      const ch = html[i];
      if (inStr) {
        if (ch === "\\") i++;
        else if (ch === '"') inStr = false;
      } else if (ch === '"') inStr = true;
      else if (ch === "[" || ch === "{") depth++;
      else if (ch === "]" || ch === "}") {
        if (--depth === 0) return JSON.parse(html.slice(start, i + 1));
      }
    }
    return null;
  }

  // ---------- captions read in the browser ----------
  // The page's player response lists caption tracks; fetching them from youtube.com itself
  // avoids the IP blocking the server hits. Returns [{start, duration, text}] or null.
  async function readCaptions(id) {
    try {
      const html = await (await fetch(`/watch?v=${id}`, { credentials: "include" })).text();
      const tracks = extractJsonArray(html, '"captionTracks":');
      if (!tracks?.length) return null;
      const track =
        tracks.find((t) => t.languageCode?.startsWith("en") && t.kind !== "asr") ||
        tracks.find((t) => t.languageCode?.startsWith("en")) ||
        tracks[0];
      if (!track) return null;
      const res = await fetch(track.baseUrl + "&fmt=json3", { credentials: "include" });
      const text = await res.text();
      if (!text) return null; // YouTube returns empty without its player's PO token
      const data = JSON.parse(text);
      const lines = (data.events || [])
        .filter((e) => e.segs)
        .map((e) => ({
          start: e.tStartMs / 1000,
          duration: (e.dDurationMs || 0) / 1000,
          text: e.segs.map((s) => s.utf8 || "").join(""),
        }))
        .filter((l) => l.text.trim());
      return lines.length ? lines : null;
    } catch {
      return null;
    }
  }

  // Fallback: open YouTube's own "Show transcript" panel and read its rows, then hide it.
  async function readTranscriptPanel() {
    const btn = document.querySelector("ytd-video-description-transcript-section-renderer button");
    if (!btn) return null;
    btn.click();
    let rows = [];
    for (let i = 0; i < 40 && !rows.length; i++) {
      await new Promise((r) => setTimeout(r, 250));
      rows = [...document.querySelectorAll("ytd-transcript-segment-renderer")];
    }
    const lines = rows
      .map((r) => ({
        start: toSeconds(r.querySelector(".segment-timestamp")?.textContent.trim() || "0:00"),
        text: r.querySelector(".segment-text")?.textContent.trim() || "",
      }))
      .filter((l) => l.text);
    lines.forEach((l, i) => (l.duration = (lines[i + 1]?.start ?? l.start + 5) - l.start));
    document
      .querySelector('ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-searchable-transcript"]')
      ?.setAttribute("visibility", "ENGAGEMENT_PANEL_VISIBILITY_HIDDEN");
    return lines.length ? lines : null;
  }

  // ---------- panel ----------
  function mountPanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.innerHTML = `
      <div class="lrag-head">
        <span class="lrag-title">🎓 Lecture RAG</span>
        <button class="lrag-collapse" title="Collapse">–</button>
      </div>
      <div class="lrag-body">
        <div class="lrag-status"></div>
        <div class="lrag-chapters"></div>
        <form class="lrag-ask">
          <input type="text" placeholder="Ask about this lecture..." />
          <button type="submit">Ask</button>
        </form>
        <div class="lrag-answer"></div>
      </div>`;

    const host = document.querySelector("#secondary-inner") || document.querySelector("#secondary");
    if (host) host.prepend(panel);
    else {
      panel.classList.add("lrag-floating");
      document.body.appendChild(panel);
    }

    panel.querySelector(".lrag-collapse").onclick = () => panel.classList.toggle("lrag-collapsed");
    panel.addEventListener("click", (e) => {
      const ts = e.target.closest("[data-t]");
      if (ts) {
        e.preventDefault();
        jump(Number(ts.dataset.t));
      }
      if (e.target.closest(".lrag-analyze")) analyze();
    });
    panel.querySelector(".lrag-ask").onsubmit = (e) => {
      e.preventDefault();
      ask(panel.querySelector(".lrag-ask input").value);
    };
    return panel;
  }

  const $ = (sel) => document.querySelector(`#${PANEL_ID} ${sel}`);
  const setStatus = (html) => ($(".lrag-status").innerHTML = html);

  function renderChapters() {
    $(".lrag-chapters").innerHTML = chapters
      .map(
        (c, i) => `
        <div class="lrag-ch" data-t="${c.seconds}" data-i="${i}">
          <span class="lrag-time">${esc(c.time)}</span>
          <div><div class="lrag-ch-title">${esc(c.title)}</div>
          <div class="lrag-ch-sum">${esc(c.summary)}</div></div>
        </div>`
      )
      .join("");
    $(".lrag-ask").style.display = chapters.length ? "flex" : "none";
  }

  // Highlight the chapter currently playing.
  function trackPlayback() {
    const v = player();
    if (!v || v.dataset.lragTracked) return;
    v.dataset.lragTracked = "1";
    v.addEventListener("timeupdate", () => {
      if (!chapters.length) return;
      let idx = 0;
      chapters.forEach((c, i) => {
        if (v.currentTime >= c.seconds) idx = i;
      });
      document.querySelectorAll(`#${PANEL_ID} .lrag-ch`).forEach((el) => {
        el.classList.toggle("lrag-active", Number(el.dataset.i) === idx);
      });
    });
  }

  // ---------- flows ----------
  async function load(id) {
    clearInterval(pollTimer);
    chapters = [];
    mountPanel();
    renderChapters();
    $(".lrag-answer").innerHTML = "";
    setStatus("Checking...");

    const r = await api(`/videos/${id}`);
    if (id !== currentVideo) return; // user navigated away meanwhile
    if (r.ok && r.data.status === "ready") return showReady(r.data);
    if (r.ok && r.data.status === "processing") return poll(id);
    if (r.status === 0) return setStatus(`<span class="lrag-err">${esc(r.data.detail)}. Is the server running?</span>`);
    setStatus(`<button class="lrag-analyze">Analyze this lecture</button>
      <div class="lrag-hint">Generates topic chapters with summaries and enables Q&amp;A.</div>`);
  }

  async function analyze() {
    const id = currentVideo;
    setStatus("Reading captions...");
    // browser first (not IP-blocked); if both fail, captions=null and the server fetches them
    const captions = (await readCaptions(id)) || (await readTranscriptPanel());
    const title = document.title.replace(/ - YouTube$/, "");
    const r = await api("/index", "POST", { source: id, captions, title });
    if (!r.ok) return setStatus(`<span class="lrag-err">${esc(r.data.detail || "Indexing failed")}</span>`);
    if (r.data.status === "ready") return load(id);
    poll(id);
  }

  function poll(id) {
    setStatus("Analyzing lecture...");
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      if (id !== currentVideo) return clearInterval(pollTimer);
      const r = await api(`/videos/${id}`);
      if (r.ok && r.data.status === "ready") {
        clearInterval(pollTimer);
        showReady(r.data);
      } else if (r.ok && r.data.status === "error") {
        clearInterval(pollTimer);
        setStatus(`<span class="lrag-err">${esc(r.data.error)}</span> <button class="lrag-analyze">Retry</button>`);
      } else if (r.ok) {
        const last = (r.data.log || []).slice(-1)[0];
        setStatus(`Analyzing lecture... <div class="lrag-hint">${esc(last || "")}</div>`);
      }
    }, 2000);
  }

  function showReady(data) {
    chapters = data.chapters || [];
    setStatus(`<div class="lrag-hint">${chapters.length} topics · click to jump</div>`);
    renderChapters();
    trackPlayback();
  }

  async function ask(question) {
    if (!question.trim()) return;
    const out = $(".lrag-answer");
    out.innerHTML = `<div class="lrag-hint">Thinking...</div>`;
    const r = await api(`/videos/${currentVideo}/ask`, "POST", { question });
    if (!r.ok) return (out.innerHTML = `<span class="lrag-err">${esc(r.data.detail || "Failed")}</span>`);
    const a = r.data;
    out.innerHTML = `
      <div class="lrag-a-text">${linkTimestamps(esc(a.answer)).replace(/\n/g, "<br>")}</div>
      <button class="lrag-jump" data-t="${a.seconds}">▶ Jump to ${esc(a.timestamp)}</button>
      <details><summary>Sources</summary>
        ${a.sources
          .map((s) => `<div class="lrag-src"><a class="lrag-ts" data-t="${s.seconds}">${esc(s.time)}</a> ${esc(s.title)}</div>`)
          .join("")}
      </details>`;
  }

  // ---------- YouTube is a single-page app: react to in-app navigation ----------
  function onNavigate() {
    const id = location.pathname === "/watch" ? videoId() : null;
    if (!id) {
      document.getElementById(PANEL_ID)?.remove();
      currentVideo = null;
      return;
    }
    if (id === currentVideo && document.getElementById(PANEL_ID)) return;
    currentVideo = id;
    // #secondary may render after navigation finishes; wait briefly for it
    let tries = 0;
    const wait = setInterval(() => {
      if (document.querySelector("#secondary") || ++tries > 20) {
        clearInterval(wait);
        load(id);
      }
    }, 250);
  }

  document.addEventListener("yt-navigate-finish", onNavigate);
  onNavigate();
})();
