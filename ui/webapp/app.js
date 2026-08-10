// CVI_ERROR_R_AUTO — SAP Fiori-style dashboard client

const $ = (id) => document.getElementById(id);

const state = {
  uploadedNotes: [],
  currentExecutionId: null,
};

// ---------- Utils ----------
function toast(msg, kind = "info") {
  console.log(`[toast:${kind}]`, msg);
}

function parseNoteNumbers(text) {
  return (text || "")
    .split(/[,\n\s]+/)
    .map((s) => s.trim())
    .filter((s) => /^\d{4,10}$/.test(s));
}

function badge(text, kind = "") {
  const classes = { ok: "badge-ok", warn: "badge-warn", err: "badge-err" };
  const cls = classes[kind] || "";
  return `<span class="badge ${cls}">${text}</span>`;
}

function statusKind(status) {
  const s = (status || "").toUpperCase();
  if (["COMPLETED"].includes(s)) return "ok";
  if (["FAILED", "ROLLED_BACK"].includes(s)) return "err";
  if (["AWAITING_APPROVAL", "IMPLEMENTING", "VALIDATING", "ANALYZING", "POST_CHECK"].includes(s))
    return "warn";
  return "";
}

// ---------- Tab switching ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    const panel = document.getElementById(`tab-${btn.dataset.tab}`);
    if (panel) panel.classList.add("active");
    onTabActivated(btn.dataset.tab);
  });
});

function onTabActivated(tab) {
  if (tab === "history") loadHistory();
  if (tab === "errors") loadErrors();
  if (tab === "transports") loadTransports();
  if (tab === "approvals") loadApprovals();
  if (tab === "audit") loadAudit();
}

// ---------- Health ----------
async function refreshHealth() {
  try {
    const r = await fetch("/health").then((r) => r.json());
    $("providerBadge").textContent = `LLM: ${r.llm_provider_active || "?"}`;
    if ((r.llm_provider_active || "") === "mock") {
      $("providerBadge").classList.add("badge-warn");
    }
    const anyReal =
      r.feature_flags && (r.feature_flags.enable_real_rfc || r.feature_flags.enable_real_snote);
    $("modeBadge").textContent = anyReal ? "Real Backend Mode" : "Simulation Mode";
  } catch (e) {
    $("providerBadge").textContent = "LLM: unknown";
  }
}

// ---------- Uploads ----------
$("noteFiles").addEventListener("change", async (ev) => {
  const files = Array.from(ev.target.files || []);
  if (!files.length) return;
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const r = await fetch("/notes/upload", { method: "POST", body: form }).then((r) => r.json());
  state.uploadedNotes = r.parsed_notes || [];
  $("uploadedNotes").textContent =
    `Uploaded ${r.files.length} file(s). Detected notes: ` +
    (state.uploadedNotes.length
      ? state.uploadedNotes.map((n) => n.note_number).join(", ")
      : "(none)");
});

// ---------- Build request ----------
function buildNotes() {
  const nums = parseNoteNumbers($("noteNumbers").value);
  const manual = nums.map((n) => ({ note_number: n, source: "manual" }));
  return [...manual, ...state.uploadedNotes];
}

function buildBaseRequest() {
  const systemType = document.querySelector('input[name="system_type"]:checked').value;
  return {
    system_type: systemType,
    system_tier: $("systemTier").value,
    requested_by: $("requestedBy").value,
    notes: buildNotes(),
    user_prompt: $("userPrompt").value.trim(),
  };
}

// ---------- Actions ----------
$("btnValidateOnly").addEventListener("click", async () => {
  const body = buildBaseRequest();
  if (!body.notes.length) return toast("Please provide at least one SAP Note", "warn");
  appendStream("• Validating...");
  const r = await fetch("/notes/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());
  state.currentExecutionId = r.execution_id;
  $("execId").textContent = r.execution_id;
  $("execStatus").innerHTML = badge("validated", "warn");
  appendStream("Validation result:\n" + JSON.stringify(r.validation, null, 2));
  showDownloads();
});

$("btnAnalyzeOnly").addEventListener("click", async () => {
  const body = buildBaseRequest();
  if (!body.notes.length) return toast("Please provide at least one SAP Note", "warn");
  appendStream("• Analyzing...");
  const r = await fetch("/notes/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());
  state.currentExecutionId = r.execution_id;
  $("execId").textContent = r.execution_id;
  $("execStatus").innerHTML = badge("analyzed", "warn");
  if (r.analysis) {
    appendStream("Analysis (LLM):\n" + (r.analysis.raw_llm_text || ""));
  }
  showDownloads();
});

$("btnAnalyzeImplement").addEventListener("click", async () => {
  const body = buildBaseRequest();
  if (!body.notes.length) return toast("Please provide at least one SAP Note", "warn");
  const release = $("releaseTransports").value === "true";
  $("execStream").textContent = "";
  $("execStatus").innerHTML = badge("running", "warn");
  appendStream(`• Starting orchestration (release_transports=${release})...`);
  try {
    await runStream(body, release);
  } catch (e) {
    appendStream("Stream failed, falling back to blocking call: " + e);
    await runBlocking(body, release);
  }
  showDownloads();
});

async function runStream(body, release) {
  const url = `/notes/implement/stream?release_transports=${release}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const p of parts) {
      const m = p.match(/^data:\s*(.*)$/s);
      if (!m) continue;
      let frame;
      try { frame = JSON.parse(m[1]); } catch { continue; }
      handleFrame(frame);
    }
  }
}

function handleFrame(frame) {
  if (frame.type === "start") {
    appendStream(`◆ start (provider=${frame.provider})`);
  } else if (frame.type === "log") {
    appendStream(`[${frame.level}] ${frame.step}: ${frame.message}`);
  } else if (frame.type === "done") {
    state.currentExecutionId = frame.execution_id;
    $("execId").textContent = frame.execution_id;
    const kind = statusKind(frame.summary.status);
    $("execStatus").innerHTML = badge(frame.summary.status, kind);
    renderSummary(frame.summary);
  } else if (frame.type === "error") {
    appendStream(`[ERROR] ${frame.message}`);
  }
}

async function runBlocking(body, release) {
  const r = await fetch(`/notes/implement?release_transports=${release}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());
  state.currentExecutionId = r.execution_id;
  $("execId").textContent = r.execution_id;
  $("execStatus").innerHTML = badge(r.status, statusKind(r.status));
  renderSummary(r.summary);
}

function renderSummary(summary) {
  if (!summary) return;
  const el = $("resultSummary");
  const rows = [];
  rows.push(`<b>Execution</b>: ${summary.execution_id}`);
  rows.push(`<b>Status</b>: ${badge(summary.status, statusKind(summary.status))}`);
  rows.push(`<b>System</b>: ${summary.system} / ${summary.tier}`);
  rows.push(`<b>Notes</b>: ${(summary.notes || []).join(", ") || "(none)"}`);
  if (summary.transports && summary.transports.length) {
    rows.push(
      `<b>Transports</b>: ` +
        summary.transports.map((t) => `<code>${t.trkorr}</code> (${t.status})`).join(", ")
    );
  }
  rows.push(`<b>Cockpit passed</b>: ${summary.cockpit_passed ? "✅" : "⚠️"}`);
  if (summary.error_summary) {
    rows.push(`<b>Error</b>: ${summary.error_summary}`);
  }
  el.innerHTML = rows.join("<br>");
}

function showDownloads() {
  if (state.currentExecutionId) $("downloadActions").style.display = "flex";
}

$("btnDownloadMd").addEventListener("click", () => downloadReport("md"));
$("btnDownloadJson").addEventListener("click", () => downloadReport("json"));
$("btnDownloadDocx").addEventListener("click", () => downloadReport("docx"));

function downloadReport(fmt) {
  if (!state.currentExecutionId) return;
  const url = `/notes/${state.currentExecutionId}/report?fmt=${fmt}`;
  window.open(url, "_blank");
}

function appendStream(msg) {
  const el = $("execStream");
  el.textContent += (el.textContent ? "\n" : "") + msg;
  el.scrollTop = el.scrollHeight;
}

// ---------- History / errors / transports / approvals / audit ----------
async function loadHistory() {
  const r = await fetch("/executions").then((r) => r.json());
  const tb = $("historyTable").querySelector("tbody");
  tb.innerHTML = "";
  (r.items || []).forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${it.execution_id}</code></td>
      <td>${it.system_type}</td>
      <td>${it.system_tier}</td>
      <td>${badge(it.status, statusKind(it.status))}</td>
      <td>${(it.notes || []).join(", ")}</td>
      <td>${it.started_at || ""}</td>
      <td>${it.finished_at || ""}</td>`;
    tb.appendChild(tr);
  });
}
$("btnRefreshHistory").addEventListener("click", loadHistory);

async function loadErrors() {
  const r = await fetch("/errors").then((r) => r.json());
  const tb = $("errorsTable").querySelector("tbody");
  tb.innerHTML = "";
  (r.items || []).forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${it.execution_id}</code></td>
      <td>${it.system}/${it.tier}</td>
      <td>${badge(it.status, "err")}</td>
      <td>${it.error_summary || ""}</td>
      <td>${it.rollback_recommendation || ""}</td>`;
    tb.appendChild(tr);
  });
}
$("btnRefreshErrors").addEventListener("click", loadErrors);

async function loadTransports() {
  const r = await fetch("/transports").then((r) => r.json());
  const tb = $("transportsTable").querySelector("tbody");
  tb.innerHTML = "";
  (r.items || []).forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${it.trkorr}</code></td>
      <td>${it.system_type}</td>
      <td>${it.system_tier}</td>
      <td>${badge(it.status, it.status === "released" ? "ok" : "warn")}</td>
      <td>${it.description}</td>
      <td><code>${it.execution_id}</code></td>`;
    tb.appendChild(tr);
  });
}
$("btnRefreshTransports").addEventListener("click", loadTransports);

async function loadApprovals() {
  const r = await fetch("/approvals").then((r) => r.json());
  const tb = $("approvalsTable").querySelector("tbody");
  tb.innerHTML = "";
  (r.items || []).forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${it.approval_id}</code></td>
      <td><code>${it.execution_id}</code></td>
      <td>${it.system_tier}</td>
      <td>${it.requester}</td>
      <td>${it.status}</td>
      <td>
        <button data-decide="${it.approval_id}" data-grant="true">Grant</button>
        <button data-decide="${it.approval_id}" data-grant="false">Reject</button>
      </td>`;
    tb.appendChild(tr);
  });
  tb.querySelectorAll("button[data-decide]").forEach((btn) => {
    btn.addEventListener("click", () => decideApproval(btn.dataset.decide, btn.dataset.grant === "true"));
  });
}
$("btnRefreshApprovals").addEventListener("click", loadApprovals);

async function decideApproval(approvalId, grant) {
  const approver = $("requestedBy").value === "demo.approver" ? "demo.approver" : "demo.admin";
  const r = await fetch(`/approvals/${approvalId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver, grant, resume: grant, release_transports: false }),
  }).then((r) => r.json()).catch((e) => ({ error: String(e) }));
  toast(JSON.stringify(r), grant ? "ok" : "warn");
  loadApprovals();
}

async function loadAudit() {
  const r = await fetch("/audit").then((r) => r.json());
  const tb = $("auditTable").querySelector("tbody");
  tb.innerHTML = "";
  (r.items || []).slice().reverse().forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.ts}</td>
      <td>${it.action}</td>
      <td>${it.actor}</td>
      <td><code>${it.execution_id || ""}</code></td>
      <td>${it.outcome || ""}</td>
      <td><code>${JSON.stringify(it.detail || {})}</code></td>`;
    tb.appendChild(tr);
  });
}
$("btnRefreshAudit").addEventListener("click", loadAudit);

// ---------- Prompt ----------
$("btnSendPrompt").addEventListener("click", async () => {
  const prompt = $("promptText").value.trim();
  if (!prompt) return;
  $("promptResponse").textContent = "…thinking…";
  const r = await fetch("/prompt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, requested_by: $("requestedBy").value }),
  }).then((r) => r.json());
  $("promptResponse").textContent =
    `[provider=${r.provider} model=${r.model} latency=${r.latency_ms}ms]\n\n${r.answer}`;
});

// ---------- Init ----------
refreshHealth();