// Gmail Operator side panel. Vanilla JS, no build step.
// SECURITY: email text is untrusted. Everything is rendered with textContent, never innerHTML.

const DEFAULTS = { baseUrl: "http://localhost:8000", token: "" };
const POLL_MS = 700;

const $ = (id) => document.getElementById(id);
const el = {
  account: $("account"), status: $("status"), notice: $("notice"), request: $("request"),
  run: $("run"), compose: $("compose"), timeline: $("timeline"), final: $("final"),
  finalText: $("final-text"), finalMeta: $("final-meta"), scroll: $("scroll"),
  gate: $("gate"), gateTitle: $("gate-title"), gateTarget: $("gate-target"), gateCall: $("gate-call"),
  gateDraftWrap: $("gate-draft-wrap"), gateTo: $("gate-to"), gateDraft: $("gate-draft"),
  approve: $("approve"), deny: $("deny"),
  settings: $("settings"), toggle: $("settings-toggle"), baseUrl: $("base-url"), token: $("token"),
  save: $("save-settings"),
};

let cfg = { ...DEFAULTS };
let runId = null;
let timer = null;
let lastWriteCount = 0;

// ---------- API ----------

async function api(path, options = {}) {
  const res = await fetch(cfg.baseUrl.replace(/\/$/, "") + path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Operator-Token": cfg.token },
  });
  let body = null;
  try { body = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) throw new Error((body && body.detail) || `Request failed (${res.status})`);
  return body;
}

// ---------- small UI helpers ----------

function setStatus(text, tone = "") { el.status.textContent = text; el.status.dataset.tone = tone; }
function showNotice(text) { el.notice.textContent = text; el.notice.hidden = !text; }

function describeCall(tool) {
  return {
    archive_email: "Archive this email",
    trash_email: "Move this email to Trash",
    label_email: "Add a label to this email",
    draft_reply: "Save a draft reply (it will not be sent)",
  }[tool] || `Run ${tool}`;
}

function shortArgs(args) {
  const parts = Object.entries(args || {}).map(([k, v]) => {
    const s = typeof v === "string" ? v : JSON.stringify(v);
    return `${k}=${s.length > 40 ? s.slice(0, 40) + "…" : s}`;
  });
  return parts.join("  ");
}

// ---------- rendering ----------

function renderTimeline(trace, pending) {
  // Pair each call with the result that follows it.
  const steps = [];
  for (const t of trace) {
    if (t.kind === "call") steps.push({ call: t, result: null });
    else if (t.kind === "result") {
      const open = [...steps].reverse().find((s) => !s.result && s.call.tool === t.tool);
      if (open) open.result = t;
    }
  }
  el.timeline.replaceChildren();
  for (const s of steps) {
    const li = document.createElement("li");
    li.className = "step" + (s.call.write ? " write" : "");
    const head = document.createElement("div");
    head.className = "step-head";
    const tool = document.createElement("span");
    tool.className = "tool"; tool.textContent = s.call.tool;
    const args = document.createElement("span");
    args.className = "args"; args.textContent = shortArgs(s.call.args);
    head.append(tool, args);
    li.append(head);

    const res = document.createElement("div");
    res.className = "result";
    if (s.result) {
      if (s.result.status === "denied") li.classList.add("denied");
      if (s.result.status === "error") li.classList.add("error");
      res.textContent = s.result.text;
      res.title = "Click to expand";
      res.addEventListener("click", () => res.classList.toggle("open"));
    } else if (pending && pending.tool === s.call.tool) {
      li.classList.add("waiting");
      res.textContent = "Waiting for your decision";
    } else {
      res.textContent = "Running…";
    }
    li.append(res);
    el.timeline.append(li);
  }
}

function renderGate(pending) {
  if (!pending) { el.gate.hidden = true; return; }
  const wasHidden = el.gate.hidden;
  const ctx = pending.context || {};
  el.gateTitle.textContent = describeCall(pending.tool);
  el.gateTarget.textContent = ctx.email_subject
    ? `${ctx.email_subject}\nFrom ${ctx.email_from}`
    : (ctx.note || "");
  el.gateTarget.style.whiteSpace = "pre-wrap";
  // The exact call, produced by the backend from the model's real arguments.
  const args = { ...pending.args };
  if (pending.tool === "draft_reply") delete args.body;
  el.gateCall.textContent = `${pending.tool}(${JSON.stringify(args)})`;
  if (pending.tool === "draft_reply") {
    el.gateTo.textContent = ctx.draft_to || "the original sender";
    el.gateDraft.textContent = pending.args.body;
    el.gateDraftWrap.hidden = false;
  } else {
    el.gateDraftWrap.hidden = true;
  }
  el.gate.hidden = false;
  el.approve.disabled = el.deny.disabled = false;
  if (wasHidden) el.gateTitle.focus(); // focus the title, not a button: no accidental Enter-approve
}

function render(state) {
  renderTimeline(state.trace, state.pending);
  renderGate(state.pending);

  const writes = state.trace.filter((t) => t.kind === "result" && t.wrote).length;
  if (writes > lastWriteCount) refreshGmailTab();
  lastWriteCount = writes;

  showNotice("");
  switch (state.status) {
    case "running": setStatus("Working…"); break;
    case "awaiting_approval": setStatus("Waiting for your decision", "wait"); break;
    case "done": setStatus(state.stop_reason ? "Stopped early" : "Done", state.stop_reason ? "bad" : ""); break;
    case "error": setStatus("Error", "bad"); showNotice(state.error || "The run failed."); break;
  }
  if (state.status === "done") {
    el.final.hidden = false;
    el.finalText.textContent = state.final || "";
    const s = state.stats || {};
    el.finalMeta.textContent =
      `${s.steps ?? 0} model steps, ${s.writes ?? 0} changes made, ${s.tokens ?? 0} tokens, ${state.elapsed_s}s`;
  } else {
    el.final.hidden = state.status !== "done";
  }
  el.scroll.scrollTop = el.scroll.scrollHeight;
}

function refreshGmailTab() {
  chrome.tabs.query({ url: "https://mail.google.com/*" }, (tabs) => {
    for (const tab of tabs || []) chrome.tabs.sendMessage(tab.id, { type: "refresh-inbox" }).catch?.(() => {});
  });
}

// ---------- polling ----------

function stopPolling() { if (timer) { clearInterval(timer); timer = null; } }

function startPolling() {
  stopPolling();
  timer = setInterval(async () => {
    try {
      const state = await api(`/runs/${runId}`);
      render(state);
      if (state.status !== "running") {
        stopPolling();
        if (state.status !== "awaiting_approval") el.run.disabled = false; // keep Run locked while a decision is pending
      }
    } catch (e) {
      stopPolling(); el.run.disabled = false;
      setStatus("Disconnected", "bad"); showNotice(e.message);
    }
  }, POLL_MS);
}

// ---------- actions ----------

el.compose.addEventListener("submit", async (e) => {
  e.preventDefault();
  const request = el.request.value.trim();
  if (request.length < 3) { showNotice("Describe what you want done, in at least a few words."); return; }
  el.run.disabled = true; showNotice("");
  el.timeline.replaceChildren(); el.final.hidden = true; el.gate.hidden = true; lastWriteCount = 0;
  setStatus("Starting…");
  try {
    const state = await api("/runs", { method: "POST", body: JSON.stringify({ request }) });
    runId = state.run_id;
    startPolling();
  } catch (err) {
    el.run.disabled = false; setStatus("Could not start", "bad"); showNotice(err.message);
  }
});

async function decide(approved) {
  el.approve.disabled = el.deny.disabled = true;
  try {
    const state = await api(`/runs/${runId}/decision`, { method: "POST", body: JSON.stringify({ approved }) });
    el.gate.hidden = true;
    render(state);
    startPolling();
  } catch (err) {
    el.approve.disabled = el.deny.disabled = false;
    showNotice(err.message);
  }
}
el.approve.addEventListener("click", () => decide(true));
el.deny.addEventListener("click", () => decide(false));

// ---------- settings + connection ----------

el.toggle.addEventListener("click", () => {
  el.settings.hidden = !el.settings.hidden;
  el.toggle.setAttribute("aria-expanded", String(!el.settings.hidden));
});

el.save.addEventListener("click", async () => {
  cfg = { baseUrl: el.baseUrl.value.trim() || DEFAULTS.baseUrl, token: el.token.value.trim() };
  await chrome.storage.local.set({ cfg });
  el.settings.hidden = true; el.toggle.setAttribute("aria-expanded", "false");
  checkConnection();
});

async function checkConnection() {
  el.account.dataset.state = "unknown"; el.account.textContent = "Checking backend…";
  if (!cfg.token) {
    el.account.dataset.state = "bad"; el.account.textContent = "Add your API token in Settings.";
    el.settings.hidden = false; el.toggle.setAttribute("aria-expanded", "true");
    return;
  }
  try {
    const h = await api("/health");
    el.account.dataset.state = "ok";
    el.account.textContent = `Connected to ${h.account}`;
  } catch (e) {
    el.account.dataset.state = "bad";
    el.account.textContent = `Backend not ready: ${e.message}`;
  }
}

(async function init() {
  const saved = await chrome.storage.local.get("cfg");
  cfg = { ...DEFAULTS, ...(saved.cfg || {}) };
  el.baseUrl.value = cfg.baseUrl; el.token.value = cfg.token;
  checkConnection();
})();
