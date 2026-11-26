// Agent-log renderers: coding-agent JSONL session logs (Claude Code, Codex, Gemini CLI, Pi).
//
// Loaded on demand by index.js, the first time one of these views is shown, with
// agent-log.css. Neither is in a folder page's load, which the plugin's folder views
// would otherwise make them (index.js, "Loading tier").
//
// Owns three views:
//   ("agent-log", "log")    — event timeline with filter chips + per-event chevron
//   ("agent-log", "charts") — chart summary fetched through the built-in
//                             agent-log data hook
//   ("agent-log", "raw")    — pretty-printed JSON
//
// It registers them over index.js's stubs, so a view looked up once they are here is the
// renderer itself. Its exports, which index.js's `loadLogRenderers` answers, are what the
// unknown-jsonl and event-log plugins draw with and what the shell's live tail appends
// events with ("Declared Dependencies" in docs/plugins.md).
//
// Helpers private to this file:
//   renderLogEvent / renderFilterBar / renderSummary / logStat / fmtDuration

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser agent-log plugin: window.metabrowser missing — SDK not loaded");
}
const filterControls = mb.filterControls;
if (!filterControls) {
  throw new Error("metabrowser agent-log plugin: filter controls missing — host assets incomplete");
}
const fc = filterControls;

// ── Per-view filter and raw-payload state ───────────────────────
const logViewStates = new WeakMap();
const chartsRenderGenerations = new WeakMap();

function nextChartsRenderGeneration(container) {
  const generation = (chartsRenderGenerations.get(container) || 0) + 1;
  chartsRenderGenerations.set(container, generation);
  return generation;
}

function newLogViewState() {
  return {
    activeKindFilters: /** @type {Set<string> | null} */ (null),
    totalKindFilters: 0,
    unbind: /** @type {(() => void) | null} */ (null),
    rawCache: new Map(),
  };
}

// A parsed log's kinds are the adapters' (`tool_call`, `init`, ...). Each is shown in the
// color of the event kind (kinds.py KINDS) it is, so one kind is one color in a badge, a
// filter, and a chart. charts.py draws the same table; tests/test_agent_kind_palette.py
// pins the two together.
const EVENT_KINDS = [
  "prompt",
  "text",
  "thinking",
  "tool-call",
  "tool-result",
  "metering",
  "control",
  "context",
  "error",
  "unknown",
];
const EVENT_KIND_OF_ADAPTER_KIND = {
  tool_call: "tool-call",
  tool_result: "tool-result",
  text: "text",
  thinking: "thinking",
  result: "metering",
  init: "context",
  system: "control",
};

function kindClassToken(kind) {
  const name = String(kind || "unknown");
  return EVENT_KIND_OF_ADAPTER_KIND[name] || (EVENT_KINDS.includes(name) ? name : "unknown");
}

function kindLabel(kind) {
  return String(kind || "unknown").replace(/[-_]+/g, " ");
}

function isUnknownKind(kind) {
  return !kind || String(kind).toLowerCase() === "unknown";
}

function fmtDuration(s) {
  if (s < 60) {
    return `${s.toFixed(1)}s`;
  }
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}m ${sec}s`;
}

function logStat(label, value) {
  return (
    '<div class="log-stat">' +
    '<span class="log-stat-label">' +
    label +
    "</span>" +
    '<span class="log-stat-value">' +
    mb.escapeHtml(String(value != null ? value : "-")) +
    "</span>" +
    "</div>"
  );
}

function eventSummaryText(evt) {
  const text = evt.summary || "";
  return isUnknownKind(evt.kind) ? text.replace(/^\[unknown\]\s*/i, "") : text;
}

function renderSummary(evt) {
  if (evt.summary_parts && evt.summary_parts.length > 0) {
    return evt.summary_parts
      .map((p) => {
        if (p.type === "omitted") {
          return `<span class="summary-omitted">${mb.escapeHtml(p.text)}</span>`;
        }
        const cls = `summary-${p.type}`;
        return `<span class="${cls}">${mb.escapeHtml(p.text)}</span>`;
      })
      .join("");
  }
  const text = eventSummaryText(evt);
  const m = text.match(/^(\[[^\]]+\])\s*(.*)/);
  if (m) {
    const rest = m[2];
    return (
      '<span class="summary-label">' +
      mb.escapeHtml(m[1]) +
      "</span>" +
      (rest ? ` <span class="summary-value">${mb.escapeHtml(rest)}</span>` : "")
    );
  }
  return mb.escapeHtml(text);
}

function renderLogEventHtml(evt, idx, state) {
  const kind = String(evt.kind || "unknown");
  const kindClass = `kind-${kindClassToken(kind)}${evt.is_error ? " error" : ""}`;
  let label = kindLabel(kind);
  if (kind === "tool_call") {
    label = "→ tool call";
  } else if (kind === "tool_result") {
    label = "← tool result";
  }

  // The per-event raw container is mounted empty; mountLogEventRaw
  // populates it lazily on first expand (see toggleEvent below).
  // Stashing evt.raw on the DOM via a data attribute would blow up
  // the HTML for big payloads, so the owning view keeps it in a
  // registry keyed by event idx instead.
  state.rawCache.set(idx, evt.raw);

  const kindHtml = isUnknownKind(kind)
    ? ""
    : `<span class="file-header-badge log-event-kind ${kindClass}">${mb.escapeHtml(label)}</span>`;
  const isFiltering =
    state.activeKindFilters && state.activeKindFilters.size < state.totalKindFilters;
  const visible = !isFiltering
    ? true
    : isUnknownKind(kind)
      ? false
      : state.activeKindFilters.has(kind);

  return (
    '<div class="log-event" data-idx="' +
    idx +
    '" data-kind="' +
    mb.escapeHtml(kind) +
    '"' +
    (visible ? "" : ' style="display: none;"') +
    ">" +
    '<div class="log-event-header disclosure-toggle" role="button" tabindex="0" aria-expanded="false">' +
    mb.icons.toggle +
    kindHtml +
    '<span class="log-event-summary" data-tip-text="' +
    mb.escapeHtml(eventSummaryText(evt)) +
    '">' +
    renderSummary(evt) +
    "</span>" +
    "</div>" +
    '<div class="log-event-raw" data-raw-idx="' +
    idx +
    '"></div>' +
    "</div>"
  );
}

function stateForDescendant(element) {
  let current = element;
  while (current) {
    const state = logViewStates.get(current);
    if (state) {
      return state;
    }
    current = current.parentElement;
  }
  return null;
}

function mountLogEventRaw(rawEl) {
  if (rawEl.dataset.mounted === "1") {
    return;
  }
  rawEl.dataset.mounted = "1";
  const idx = parseInt(rawEl.getAttribute("data-raw-idx") || "-1", 10);
  const raw = stateForDescendant(rawEl)?.rawCache.get(idx);
  if (raw === undefined) {
    return;
  }

  if (raw && typeof raw === "object") {
    // An object payload is the structured plugin's tree (`requires` in manifest.toml),
    // loaded with the first payload opened and shared by every later one.
    const inner = window.document.createElement("div");
    rawEl.appendChild(inner);
    mb.plugins
      .load("structured")
      .then((structured) => {
        structured.renderInlineTree(inner, raw, {
          virtualize: false,
          // Per-event payloads are bounded by jsonl_view's 8 KiB cap
          // (_LARGE_FILE_PER_EVENT_RAW), so even a generous budget
          // can't blow the row count up. Bias toward full visibility
          // — the operator already had to click the event open, the
          // last thing they want is another click for every nested
          // object inside the payload.
          maxLines: 300,
          maxExpandThreshold: 200,
          indentChars: 2,
        });
      })
      .catch((err) => {
        // The flat block below, on any loading or rendering error.
        inner.remove();
        console.warn("structured inline tree failed; falling back to flat JSON", err);
        mountFlatRaw(rawEl, raw);
      });
    return;
  }
  mountFlatRaw(rawEl, raw);
}

// A single <pre><code> block. Mounted at once, for a string payload, it is highlighted by
// the shell's highlightCode() pass, which toggleEvent schedules after the mount. Mounted
// after a structured tree failed to load, it comes after that pass and stays plain: an
// error path, where readable text is what matters.
function mountFlatRaw(rawEl, raw) {
  const text = typeof raw === "string" ? raw : JSON.stringify(raw, null, 2);
  rawEl.innerHTML = `<pre><code class="language-json">${mb.escapeHtml(text)}</code></pre>`;
}

// Expose for the shell's toggleEvent() to call when an event is
// first expanded. The shell looks this up at click time, so the
// load-order doesn't matter.
if (!window.metabrowserAgentLog) {
  window.metabrowserAgentLog = {};
}
window.metabrowserAgentLog.mountLogEventRaw = mountLogEventRaw;

function renderFilterBar(events, state) {
  const counts = {};
  for (let i = 0; i < events.length; i++) {
    const k = String(events[i].kind || "unknown");
    if (isUnknownKind(k)) {
      continue;
    }
    counts[k] = (counts[k] || 0) + 1;
  }
  const kindOrder = ["thinking", "text", "tool_call", "tool_result", "system", "init", "result"];
  const kinds = kindOrder.filter((k) => counts[k]);
  Object.keys(counts).forEach((k) => {
    if (kinds.indexOf(k) === -1) {
      kinds.push(k);
    }
  });
  if (kinds.length <= 1) {
    state.activeKindFilters = null;
    state.totalKindFilters = 0;
    return "";
  }

  state.activeKindFilters = new Set(kinds);
  state.totalKindFilters = kinds.length;

  const options = kinds.map((kind) => ({
    value: kind,
    label: `${kindLabel(kind)} (${mb.formatInteger(counts[kind])})`,
  }));
  return (
    '<div class="agent-log-filter-bar">' +
    fc.groupHtml({
      key: "agent-event-kind",
      select: "many",
      layout: "wrap",
      label: "Event types",
      options,
      value: kinds,
    }) +
    "</div>"
  );
}

function toggleKindFilter(kind, root, state) {
  if (!state.activeKindFilters) {
    return;
  }
  const btn = Array.from(
    root.querySelectorAll('[data-chip-key="agent-event-kind"][data-chip-value]'),
  ).find((candidate) => candidate.getAttribute("data-chip-value") === kind);
  if (!btn) {
    return;
  }
  if (state.activeKindFilters.has(kind)) {
    state.activeKindFilters.delete(kind);
    btn.setAttribute("aria-pressed", "false");
  } else {
    state.activeKindFilters.add(kind);
    btn.setAttribute("aria-pressed", "true");
  }
  const isFiltering = state.activeKindFilters.size < state.totalKindFilters;
  root.querySelectorAll(".log-event[data-kind]").forEach((el) => {
    const eventKind = el.getAttribute ? el.getAttribute("data-kind") : el.dataset.kind;
    const visible = isUnknownKind(eventKind)
      ? !isFiltering
      : state.activeKindFilters.has(eventKind);
    el.style.display = visible ? "" : "none";
  });
}

// The filter bar's own element is bound, not the log around it (docs/plugins.md, "Menus");
// a log with one kind of event draws no bar.
function bindFilterBar(container, state) {
  const bar = container.querySelector(".agent-log-filter-bar");
  if (bar === null) {
    return () => {};
  }
  return fc.bind(bar, {
    onChange(key, value, select) {
      if (key !== "agent-event-kind" || select !== "many") {
        return;
      }
      toggleKindFilter(value, container, state);
    },
  });
}

// ── Renderers ───────────────────────────────────────────────────

function renderLogHtml(data, state) {
  const s = data.summary || {};
  let summary = '<div class="log-summary">';
  if (s.model) {
    summary += logStat("Model", s.model);
  }
  if (s.duration_s != null) {
    summary += logStat("Duration", fmtDuration(s.duration_s));
  }
  if (s.cost_usd != null) {
    summary += logStat("Cost", `$${s.cost_usd.toFixed(2)}`);
  }
  summary += logStat("Tool calls", mb.formatInteger(s.tool_calls));
  summary += logStat("Events", mb.formatInteger(s.total_events));
  if (s.errors > 0) {
    summary += logStat("Errors", mb.formatInteger(s.errors));
  }
  if (s.lines_skipped) {
    summary += logStat(
      "Lines skipped",
      `${mb.formatInteger(s.lines_skipped)} of ${mb.formatInteger(s.lines_total)} (oversized)`,
    );
  }
  summary += "</div>";
  const filterBar = renderFilterBar(data.events || [], state);
  const events = (data.events || []).map((evt, i) => renderLogEventHtml(evt, i, state));
  return summary + filterBar + events.join("");
}

function renderRawHtml(data) {
  const raw = data.raw_text || "";
  const cls = mb.isLargeTextPreview({ size: raw.length, content: raw })
    ? "plaintext no-highlight"
    : "language-json";
  let trailer = "";
  const t = data.raw_truncation;
  if (t) {
    const skipped =
      t.lines_skipped > 0
        ? ` ${t.lines_skipped} oversized ${t.lines_skipped === 1 ? "line was" : "lines were"} skipped.`
        : "";
    trailer =
      "\n\n… Raw content truncated. Showing at most " +
      mb.formatSize(t.cap_bytes) +
      " of " +
      mb.formatSize(t.file_bytes) +
      "." +
      skipped;
  }
  return mb.wrapWithCopy(
    '<pre class="code-block"><code class="' +
      cls +
      '">' +
      mb.escapeHtml(raw + trailer) +
      "</code></pre>",
  );
}

function renderLog(container, ctx) {
  disposeLog(container);
  const state = newLogViewState();
  logViewStates.set(container, state);
  mb.perf.measure("renderAgentLog:log", () => {
    container.innerHTML = renderLogHtml(ctx.raw, state);
    const unbindFilters = bindFilterBar(container, state);
    // One delegated listener opens an event, rather than an inline handler on each
    // header: the page policy for an untrusted source runs no inline handler.
    const toggle = (event) => {
      const target = event.target;
      const header =
        target && typeof target.closest === "function" ? target.closest(".log-event-header") : null;
      if (header && container.contains(header)) {
        window.toggleEvent(header);
        header.setAttribute(
          "aria-expanded",
          String(header.parentElement.classList.contains("expanded")),
        );
        return true;
      }
      return false;
    };
    // A header is a div, not a button, so the keys a button answers to are this
    // listener's. preventDefault keeps Space from scrolling. Like every disclosure
    // toggle it selects no text; the event's own text is in the body it opens.
    const toggleFromKey = (event) => {
      const plain = !(event.altKey || event.ctrlKey || event.metaKey || event.shiftKey);
      if ((event.key === "Enter" || event.key === " ") && plain && !event.repeat) {
        if (toggle(event)) {
          event.preventDefault();
        }
      }
    };
    container.addEventListener("click", toggle);
    container.addEventListener("keydown", toggleFromKey);
    state.unbind = () => {
      unbindFilters?.();
      container.removeEventListener("click", toggle);
      container.removeEventListener("keydown", toggleFromKey);
    };
  });
}

function disposeLog(container) {
  if (!container) {
    return;
  }
  const state = logViewStates.get(container);
  if (!state) {
    return;
  }
  if (state.unbind) {
    state.unbind();
  }
  state.rawCache.clear();
  logViewStates.delete(container);
}

function renderLogEvent(container, event, index) {
  const state = logViewStates.get(container);
  return state ? renderLogEventHtml(event, index, state) : "";
}

function renderRaw(container, ctx) {
  mb.perf.measure("renderAgentLog:raw", () => {
    container.innerHTML = renderRawHtml(ctx.raw);
  });
}

async function renderCharts(container, ctx) {
  const generation = nextChartsRenderGeneration(container);
  container.innerHTML =
    '<div class="charts-placeholder preview-empty mb-delayed-loading">' +
    '<span class="sr-only">Loading charts…</span></div>';
  // Chart.js is on the on-demand tier, so this view pays for it and no
  // other document does. The payload and bundle are independent network
  // work, so begin them together rather than putting one waterfall behind
  // the other. Resolves immediately once the bundle has been loaded.
  const [chartData] = await Promise.all([
    mb.fetchPluginData("agents", "charts", { path: ctx.path }),
    mb.ensureAsset("chart"),
  ]);
  if (generation !== chartsRenderGenerations.get(container)) {
    return;
  }
  if (!window.MetabrowserCharts) {
    throw new Error("Chart rendering is unavailable.");
  }
  window.MetabrowserCharts.renderPayload(container, chartData);
}

function disposeCharts(container) {
  nextChartsRenderGeneration(container);
  window.MetabrowserCharts?.dispose(container);
}

// ── Exports + registration ──────────────────────────────────────

// What index.js's `loadLogRenderers` answers. renderLogEvent is for the shell's live
// stream handler, which appends one batch of new events to an already-rendered log
// pane without re-rendering the whole thing.
export { disposeCharts, disposeLog, renderCharts, renderLog, renderLogEvent, renderRaw };

mb.registerView("agent-log", "log", { render: renderLog, dispose: disposeLog });
mb.registerView("agent-log", "charts", {
  render: renderCharts,
  dispose: disposeCharts,
});
mb.registerView("agent-log", "raw", { render: renderRaw });
