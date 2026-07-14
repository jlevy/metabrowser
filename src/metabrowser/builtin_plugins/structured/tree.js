// Structured plugin — Tree renderer + windowed virtualization.
//
// Loads after preview.js (manifest extra_scripts order). Reads the
// pure utility functions off __structuredPreview and emits DOM into
// the container the shell hands us at render time.
//
// Public surface (assigned to window.__structuredTree):
//   materializeRows(parsed, expandedPaths) -> Row[]
//   renderInlineTree(container, parsed, opts) -> {dispose}
//     opts: {maxLines, maxExpandThreshold, indentChars, virtualize}
//
// renderInlineTree is the stable embedding contract that other
// plugins (agent-log, future schema-aware variants) consume via
// mb.builtins.structured.renderInlineTree.
((global) => {
  var pv = global.__structuredPreview;
  if (!pv) {
    console.error(
      "structured/tree.js: __structuredPreview missing — preview.js did not load first",
    );
    return;
  }

  var DEFAULT_ROW_HEIGHT_PX = 18;
  var DEFAULT_OVERSCAN = 6;
  var DEFAULT_INLINE_PREVIEW_WIDTH = 80;
  // Below this row count we skip virtualization — the DOM cost is
  // trivial and the windowed-list scroll-listener overhead is wasted.
  var VIRTUALIZE_ROW_THRESHOLD = 200;

  function escHtml(s) {
    if (s === null || s === undefined) {
      return "";
    }
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Row materialization ─────────────────────────────────────────
  //
  // A flat list of rows derived from (parsed, expandedPaths). Each
  // row is one rendered <div class="srow"> in the DOM. Order matches
  // source-document order; key order is preserved from the parsed
  // input.

  function _isContainer(v) {
    return Array.isArray(v) || (v !== null && typeof v === "object");
  }

  function _entriesOf(v) {
    if (Array.isArray(v)) {
      var out = [];
      for (var i = 0; i < v.length; i++) {
        out.push({ key: i, value: v[i], isArrayIndex: true });
      }
      return out;
    }
    var keys = Object.keys(v);
    var oo = [];
    for (var k = 0; k < keys.length; k++) {
      oo.push({ key: keys[k], value: v[keys[k]], isArrayIndex: false });
    }
    return oo;
  }

  function _childPath(parentPath, entry) {
    return entry.isArrayIndex ? `${parentPath}[${entry.key}]` : `${parentPath}.${entry.key}`;
  }

  function materializeRows(parsed, expandedPaths) {
    var rows = [];

    function walk(value, key, isArrayIndex, level, path) {
      if (!_isContainer(value)) {
        rows.push({
          path: path,
          level: level,
          kind: isArrayIndex ? "item" : "kv",
          key: isArrayIndex ? null : String(key),
          value: value,
          isArrayIndex: isArrayIndex,
        });
        return;
      }
      var entries = _entriesOf(value);
      var isExpanded = expandedPaths.has(path);
      var isArray = Array.isArray(value);
      if (entries.length === 0) {
        rows.push({
          path: path,
          level: level,
          kind: "empty",
          key: key === null ? null : String(key),
          isArrayIndex: isArrayIndex,
          isArray: isArray,
        });
        return;
      }
      rows.push({
        path: path,
        level: level,
        kind: "open",
        key: key === null ? null : String(key),
        isArrayIndex: isArrayIndex,
        isArray: isArray,
        childCount: entries.length,
        expanded: isExpanded,
        value: !isExpanded ? value : undefined,
      });
      if (!isExpanded) {
        return;
      }
      for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        walk(e.value, e.key, e.isArrayIndex, level + 1, _childPath(path, e));
      }
    }

    if (!_isContainer(parsed)) {
      rows.push({
        path: "$",
        level: 0,
        kind: "kv",
        key: null,
        value: parsed,
        isArrayIndex: false,
      });
      return rows;
    }
    walk(parsed, null, false, 0, "$");
    return rows;
  }

  // ── Row rendering ───────────────────────────────────────────────

  function _renderPreviewParts(parts) {
    var html = "";
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      switch (p.kind) {
        case "bracket":
        case "punct":
          html += `<span class="tok-punct">${escHtml(p.text)}</span>`;
          break;
        case "key":
          html += `<span class="tok-key">${escHtml(p.text)}</span>`;
          break;
        case "value":
          html +=
            '<span class="' +
            escHtml(p.colorClass || "tok-string") +
            '">' +
            escHtml(p.text) +
            "</span>";
          break;
        case "nested":
          html += `<span class="tok-summary">${escHtml(p.text)}</span>`;
          break;
        case "more":
          // "(N more)" is chrome metadata, not content — sans-serif.
          html += `<span class="tok-meta">${escHtml(p.text)}</span>`;
          break;
        default:
          html += escHtml(p.text || "");
      }
    }
    return html;
  }

  function renderRowHtml(row, indentChars) {
    var indentStyle = pv.calculateIndentStyle(row.level, indentChars);
    var stylePart = ` style="padding-left:${indentStyle.paddingLeft};"`;
    var rowClass = "srow";
    var chevronHtml = "";
    if (row.kind === "open") {
      rowClass += " srow-container";
      rowClass += row.expanded ? " srow-expanded" : " srow-collapsed";
      chevronHtml = '<span class="srow-chevron" aria-hidden="true">▸</span>';
    } else if (row.kind === "empty") {
      rowClass += " srow-empty";
      chevronHtml = '<span class="srow-chevron srow-chevron-empty"></span>';
    } else {
      chevronHtml = '<span class="srow-chevron srow-chevron-leaf"></span>';
    }

    var keyHtml = "";
    if (row.key !== null && row.key !== undefined) {
      keyHtml =
        '<span class="tok-key">' +
        escHtml(row.key) +
        "</span>" +
        '<span class="tok-punct">: </span>';
    } else if (row.isArrayIndex) {
      keyHtml = '<span class="tok-punct">- </span>';
    }

    var bodyHtml = "";
    if (row.kind === "kv" || row.kind === "item") {
      var fv = pv.formatValue(row.value);
      bodyHtml = `<span class="${fv.colorClass}">${escHtml(fv.text)}</span>`;
    } else if (row.kind === "open") {
      if (row.expanded) {
        var label = row.isArray ? `${row.childCount} items` : `${row.childCount} keys`;
        bodyHtml =
          '<span class="tok-count">' +
          '<span class="tok-punct">' +
          (row.isArray ? "[" : "{") +
          "</span>" +
          '<span class="tok-count-label">' +
          escHtml(label) +
          "</span>" +
          '<span class="tok-punct">' +
          (row.isArray ? "]" : "}") +
          "</span>" +
          "</span>";
      } else {
        var pr = pv.generateStructuredPreview(row.value, {
          maxWidth: DEFAULT_INLINE_PREVIEW_WIDTH,
        });
        bodyHtml = _renderPreviewParts(pr.parts);
      }
    } else if (row.kind === "empty") {
      bodyHtml = `<span class="tok-summary">${row.isArray ? "[]" : "{}"}</span>`;
    }

    return (
      '<div class="' +
      rowClass +
      '" data-path="' +
      escHtml(row.path) +
      '"' +
      stylePart +
      ">" +
      chevronHtml +
      '<span class="srow-content">' +
      keyHtml +
      bodyHtml +
      "</span>" +
      "</div>"
    );
  }

  // ── Windowed virtualization ─────────────────────────────────────

  function _readRowHeight(container) {
    var styles = global.getComputedStyle ? global.getComputedStyle(container) : null;
    if (!styles) {
      return DEFAULT_ROW_HEIGHT_PX;
    }
    var raw = styles.getPropertyValue("--tree-row-height").trim();
    if (!raw) {
      return DEFAULT_ROW_HEIGHT_PX;
    }
    var n = parseFloat(raw);
    return Number.isFinite(n) && n > 0 ? n : DEFAULT_ROW_HEIGHT_PX;
  }

  function _renderVirtualWindow(state) {
    var rowH = state.rowHeight;
    var scrollTop = state.viewport.scrollTop;
    var clientH = state.viewport.clientHeight || rowH * 20;
    var firstIdx = Math.max(0, Math.floor(scrollTop / rowH) - state.overscan);
    var lastIdx = Math.min(
      state.rows.length,
      Math.ceil((scrollTop + clientH) / rowH) + state.overscan,
    );
    var html = "";
    for (var i = firstIdx; i < lastIdx; i++) {
      var row = state.rows[i];
      var topPx = i * rowH;
      html +=
        '<div class="srow-slot" style="position:absolute;top:' +
        topPx +
        "px;left:0;right:0;height:" +
        rowH +
        'px;">' +
        renderRowHtml(row, state.indentChars) +
        "</div>";
    }
    state.spacer.innerHTML = html;
  }

  function _renderFlat(state) {
    var html = "";
    for (var i = 0; i < state.rows.length; i++) {
      html += renderRowHtml(state.rows[i], state.indentChars);
    }
    state.viewport.innerHTML = html;
  }

  function _handleClick(ev, state, rebuildFn) {
    var target = ev.target;
    while (target && target !== state.viewport) {
      if (target.classList?.contains("srow")) {
        if (!target.classList.contains("srow-container")) {
          return;
        }
        var path = target.getAttribute("data-path");
        if (!path) {
          return;
        }
        if (state.expandedPaths.has(path)) {
          state.expandedPaths.delete(path);
        } else {
          state.expandedPaths.add(path);
        }
        rebuildFn();
        return;
      }
      target = target.parentNode;
    }
  }

  // ── Public renderer ─────────────────────────────────────────────

  function renderInlineTree(container, parsed, opts) {
    opts = opts || {};
    var virtualize = opts.virtualize !== false; // default true
    var maxLines = opts.maxLines || 60;
    var maxExpandThreshold = opts.maxExpandThreshold || 80;
    var indentChars = opts.indentChars || 2;

    var expandedPaths = pv.calculateOptimalExpansion(parsed, {
      maxLines: maxLines,
      maxExpandThreshold: maxExpandThreshold,
      indentChars: indentChars,
    });

    var rows = materializeRows(parsed, expandedPaths);

    container.classList.add("structured-tree");
    container.innerHTML = "";

    var useVirtualization = virtualize && rows.length >= VIRTUALIZE_ROW_THRESHOLD;

    if (!useVirtualization) {
      var flatViewport = global.document.createElement("div");
      flatViewport.className = "tree-viewport tree-viewport-flat";
      container.appendChild(flatViewport);
      var state = {
        rows: rows,
        viewport: flatViewport,
        indentChars: indentChars,
        expandedPaths: expandedPaths,
      };
      _renderFlat(state);
      function rebuildFlat() {
        state.rows = materializeRows(parsed, state.expandedPaths);
        _renderFlat(state);
      }
      flatViewport.addEventListener("click", (ev) => {
        _handleClick(ev, state, rebuildFlat);
      });
      return {
        dispose: () => {
          // No window-level listeners attached; container detaches on
          // file change, taking the listeners with it.
        },
      };
    }

    // Virtualized path.
    var viewport = global.document.createElement("div");
    viewport.className = "tree-viewport";
    var spacer = global.document.createElement("div");
    spacer.className = "tree-spacer";
    spacer.style.position = "relative";
    var rowHeight = _readRowHeight(viewport) || DEFAULT_ROW_HEIGHT_PX;
    spacer.style.height = `${rows.length * rowHeight}px`;
    viewport.appendChild(spacer);
    container.appendChild(viewport);

    var vstate = {
      rows: rows,
      viewport: viewport,
      spacer: spacer,
      rowHeight: rowHeight,
      overscan: DEFAULT_OVERSCAN,
      indentChars: indentChars,
      expandedPaths: expandedPaths,
    };

    function rebuild() {
      vstate.rows = materializeRows(parsed, vstate.expandedPaths);
      spacer.style.height = `${vstate.rows.length * vstate.rowHeight}px`;
      _renderVirtualWindow(vstate);
    }

    _renderVirtualWindow(vstate);

    var scrollListener = () => {
      _renderVirtualWindow(vstate);
    };
    viewport.addEventListener("scroll", scrollListener, { passive: true });
    viewport.addEventListener("click", (ev) => {
      _handleClick(ev, vstate, rebuild);
    });

    return {
      dispose: () => {
        viewport.removeEventListener("scroll", scrollListener);
      },
    };
  }

  global.__structuredTree = {
    materializeRows: materializeRows,
    renderInlineTree: renderInlineTree,
  };
})(typeof window !== "undefined" ? window : globalThis);
