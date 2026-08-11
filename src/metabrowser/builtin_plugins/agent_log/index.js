// Agent-log built-in plugin — renders coding-agent JSONL session logs
// (Claude Code, Gemini CLI, Pi).
//
// Owns three views:
//   ("agent-log", "log")    — event timeline with filter chips + per-event chevron
//   ("agent-log", "charts") — chart summary fetched through the built-in
//                             agent-log data hook
//   ("agent-log", "raw")    — pretty-printed JSON
//
// The renderers below also feed the unknown-jsonl plugin via
// mb.builtins.agentLog.{renderLog, renderRaw} — same body, different kind.
// Built-ins discover before entry-point + local plugins, so the namespace
// is set before unknown_jsonl/index.js runs.
//
// Helpers private to this plugin:
//   renderLogEvent / renderFilterBar / renderSummary / logStat / fmtDuration

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser agent-log plugin: window.metabrowser missing — SDK not loaded");
    return;
  }
  const filterControls = mb.filterControls;
  if (!filterControls) {
    console.error("metabrowser agent-log plugin: filter controls missing — host assets incomplete");
    return;
  }
  const fc = filterControls;

  // ── Per-plugin filter state ─────────────────────────────────────
  let activeKindFilters = null; // Set<string> | null
  let totalKindFilters = 0;
  let logFilterUnbind = null;
  let chartsRenderGeneration = 0;

  function kindClassToken(kind) {
    return String(kind || "unknown").replace(/[^a-z0-9_-]/gi, "-");
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

  function renderLogEvent(evt, idx) {
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
    // the HTML for big payloads, so we keep it in a module-scope
    // registry keyed by event idx instead.
    _logEventRawCache.set(idx, evt.raw);

    const kindHtml = isUnknownKind(kind)
      ? ""
      : `<span class="log-event-kind ${kindClass}">${mb.escapeHtml(label)}</span>`;

    return (
      '<div class="log-event" data-idx="' +
      idx +
      '" data-kind="' +
      mb.escapeHtml(kind) +
      '">' +
      '<div class="log-event-header" onclick="toggleEvent(this)">' +
      mb.icons.chevron +
      kindHtml +
      '<span class="log-event-summary" title="' +
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

  // Module-scope cache of evt.raw payloads, indexed by event idx.
  // toggleEvent() in the shell pulls this on first-expand and mounts
  // an inline structured tree (if the structured plugin is present)
  // or falls back to a flat JSON block.
  const _logEventRawCache = new Map();

  function mountLogEventRaw(rawEl) {
    if (rawEl.dataset.mounted === "1") {
      return;
    }
    rawEl.dataset.mounted = "1";
    const idx = parseInt(rawEl.getAttribute("data-raw-idx") || "-1", 10);
    const raw = _logEventRawCache.get(idx);
    if (raw === undefined) {
      return;
    }

    // Render-time-only namespace read: mb.builtins.structured may not
    // exist (plugin disabled / removed from install set). Fall back to
    // the flat <pre><code language-json> block in that case.
    if (mb.builtins?.structured && raw && typeof raw === "object") {
      const inner = window.document.createElement("div");
      rawEl.appendChild(inner);
      try {
        mb.builtins.structured.renderInlineTree(inner, raw, {
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
        return;
      } catch (err) {
        // Fall through to the flat block below on any rendering error.
        rawEl.removeChild(inner);
        console.warn("structured inline tree failed; falling back to flat JSON", err);
      }
    }
    // Fallback path: render a single <pre><code> block. Highlight.js
    // picks it up via the existing highlightCode() pass.
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

  function renderFilterBar(events) {
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
      activeKindFilters = null;
      totalKindFilters = 0;
      return "";
    }

    activeKindFilters = new Set(kinds);
    totalKindFilters = kinds.length;

    const options = kinds.map((kind) => ({
      value: kind,
      label: `${kindLabel(kind)} (${counts[kind].toLocaleString()})`,
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

  function toggleKindFilter(kind, root) {
    if (!activeKindFilters) {
      return;
    }
    const btn = Array.from(
      root.querySelectorAll('[data-chip-key="agent-event-kind"][data-chip-value]'),
    ).find((candidate) => candidate.getAttribute("data-chip-value") === kind);
    if (!btn) {
      return;
    }
    if (activeKindFilters.has(kind)) {
      activeKindFilters.delete(kind);
      btn.setAttribute("aria-pressed", "false");
    } else {
      activeKindFilters.add(kind);
      btn.setAttribute("aria-pressed", "true");
    }
    const isFiltering = activeKindFilters.size < totalKindFilters;
    root.querySelectorAll(".log-event[data-kind]").forEach((el) => {
      const eventKind = el.getAttribute ? el.getAttribute("data-kind") : el.dataset.kind;
      const visible = isUnknownKind(eventKind) ? !isFiltering : activeKindFilters.has(eventKind);
      el.style.display = visible ? "" : "none";
    });
  }

  function bindFilterBar(container) {
    return fc.bind(container, {
      onChange(key, value, select) {
        if (key !== "agent-event-kind" || select !== "many") {
          return;
        }
        toggleKindFilter(value, container);
      },
    });
  }

  // ── Renderers ───────────────────────────────────────────────────

  function renderLogHtml(data) {
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
    summary += logStat("Tool calls", s.tool_calls);
    summary += logStat("Events", s.total_events);
    if (s.errors > 0) {
      summary += logStat("Errors", s.errors);
    }
    if (s.lines_skipped) {
      summary += logStat("Lines skipped", `${s.lines_skipped} of ${s.lines_total} (oversized)`);
    }
    summary += "</div>";
    const filterBar = renderFilterBar(data.events || []);
    const events = (data.events || []).map((evt, i) => renderLogEvent(evt, i));
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
    if (logFilterUnbind) {
      logFilterUnbind();
      logFilterUnbind = null;
    }
    // Drop stale per-event raw payloads from the previously rendered
    // log; renderLogHtml repopulates them fresh below. Without this
    // the cache grows across the whole session.
    _logEventRawCache.clear();
    mb.perf.measure("renderAgentLog:log", () => {
      container.innerHTML = renderLogHtml(ctx.raw);
      logFilterUnbind = bindFilterBar(container);
    });
  }

  function disposeLog() {
    if (logFilterUnbind) {
      logFilterUnbind();
      logFilterUnbind = null;
    }
    activeKindFilters = null;
    totalKindFilters = 0;
    _logEventRawCache.clear();
  }

  function renderRaw(container, ctx) {
    mb.perf.measure("renderAgentLog:raw", () => {
      container.innerHTML = renderRawHtml(ctx.raw);
    });
  }

  async function renderCharts(container, ctx) {
    const generation = ++chartsRenderGeneration;
    container.innerHTML = '<div class="charts-placeholder preview-empty">Loading charts…</div>';
    const chartData = await mb.fetchPluginData("agent-log", "charts", {
      path: ctx.path,
    });
    if (generation !== chartsRenderGeneration) {
      return;
    }
    if (!window.MetabrowserCharts) {
      throw new Error("Chart rendering is unavailable.");
    }
    window.MetabrowserCharts.renderPayload(container, chartData);
  }

  function disposeCharts() {
    chartsRenderGeneration += 1;
    window.MetabrowserCharts?.dispose();
  }

  // ── Reusable namespace + registration ───────────────────────────

  if (!mb.builtins) {
    mb.builtins = {};
  }
  mb.builtins.agentLog = {
    renderLog: renderLog,
    disposeLog: disposeLog,
    renderRaw: renderRaw,
    renderCharts: renderCharts,
    // Single-event renderer exposed for the shell's SSE live-stream
    // handler — appending one batch of new events to an already-
    // rendered log pane without re-rendering the whole thing.
    renderLogEvent: renderLogEvent,
  };

  mb.registerView("agent-log", "log", { render: renderLog, dispose: disposeLog });
  mb.registerView("agent-log", "charts", {
    render: renderCharts,
    dispose: disposeCharts,
  });
  mb.registerView("agent-log", "raw", { render: renderRaw });
})();
