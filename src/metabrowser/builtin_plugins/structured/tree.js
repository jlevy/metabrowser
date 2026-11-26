// Structured plugin — Tree renderer + windowed virtualization.
//
// Loads after preview.js (manifest extra_scripts order). Reads the
// pure utility functions off __structuredPreview and emits DOM into
// the container the shell hands us at render time.
//
// Public surface (assigned to window.__structuredTree):
//   materializeRows(parsed, expandedPaths, opts?) -> Row[]
//     opts: {path, level, key, isArrayIndex, limit, shown}; see materializeRows
//   renderRowHtml(row, indentChars) -> string
//   renderInlineTree(container, parsed, opts) -> {dispose}
//     opts: {maxLines, maxExpandThreshold, indentChars, virtualize}
//   expansion: the file view's first-draw expansion options
//
// A row's path is positional: the root is "$" and each child appends "/" and its
// index among its parent's entries, so "$/3/0" is the first entry of the root's fourth.
// A path is as long as the value is deep, whatever its keys are, and two entries never
// share one (mb-8274 review B1 and A14).
//
// renderInlineTree is the stable embedding contract that other
// plugins (agent-log, future schema-aware variants) consume via
// the exports of structured/index.js. materializeRows, renderRowHtml, a row's
// fields (`change`, `text`, `hidden` and `changed` among them), and the "more" row are
// internal to Metabrowser's own views (the rendered diff, diff-structured.js) and change
// with them.
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
  // The file view's first-draw expansion, which a pull request's rendered diff reads
  // too (diff-structured.js), so a value opens alike in both. The JsonViewer reference
  // picked 8 lines for a sidebar embed; the structured browser is a full pane. With
  // virtualization the DOM cost of an open row bottoms out at zero (only visible rows
  // are mounted), so maxLines is a UX choice: how many lines of context the reader
  // expects on first paint. 500 makes the 16k-node MSFT bundle browseable without a
  // click on every nested object; maxExpandThreshold keeps a 5,000-item list closed.
  var EXPANSION = Object.freeze({ maxLines: 500, maxExpandThreshold: 200, indentChars: 2 });

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

  // A child's path: its parent's and its position among the parent's entries.
  function _childPath(parentPath, index) {
    return `${parentPath}/${index}`;
  }

  // The rows of `parsed` with the containers at `expandedPaths` open, in document order.
  // `opts` places the value inside a larger tree, as a rendered diff draws one entry's
  // value under its key: `path` (default "$"), `level`, and the root row's `key` and
  // `isArrayIndex`. `limit` bounds the children an open container draws, and `shown`
  // maps a container's path to how many it draws instead; the rest are one "more" row
  // (path: the container's and "/+", `hidden`: how many), which the diff opens a page of
  // at a time. Without a limit every child is drawn, as the file view draws them.
  function materializeRows(parsed, expandedPaths, opts) {
    opts = opts || {};
    var rows = [];
    var limit = opts.limit === undefined ? Infinity : opts.limit;
    var shown = opts.shown;

    function walk(value, key, isArrayIndex, level, path) {
      if (!_isContainer(value)) {
        rows.push({
          path: path,
          level: level,
          kind: isArrayIndex ? "item" : "kv",
          key: isArrayIndex || key === null ? null : String(key),
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
      var drawn = Math.min(entries.length, shown?.get(path) || limit);
      for (var i = 0; i < drawn; i++) {
        var e = entries[i];
        walk(e.value, e.key, e.isArrayIndex, level + 1, _childPath(path, i));
      }
      if (drawn < entries.length) {
        rows.push({
          path: `${path}/+`,
          level: level + 1,
          kind: "more",
          key: null,
          isArrayIndex: false,
          hidden: entries.length - drawn,
        });
      }
    }

    walk(
      parsed,
      opts.key === undefined ? null : opts.key,
      opts.isArrayIndex === true,
      opts.level || 0,
      opts.path || "$",
    );
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

  // The registry's chevron (the SDK's `mb.icons.toggle`), the one every disclosure in
  // the product wears. A module driven without the shell has no SDK, so no chevron; the
  // shell always ships it, and the icon catalog (docs/design-system-icons.md) lists every
  // typed glyph, so a stand-in character is not added here.
  function disclosureIcon() {
    return global.metabrowser?.icons.toggle || "";
  }

  function renderRowHtml(row, indentChars) {
    var indentStyle = pv.calculateIndentStyle(row.level, indentChars);
    var stylePart = ` style="padding-left:${indentStyle.paddingLeft};"`;
    var rowClass = "srow";
    var chevronHtml = "";
    if (row.kind === "open") {
      rowClass += " srow-container disclosure-toggle";
      rowClass += row.expanded ? " srow-expanded" : " srow-collapsed";
      chevronHtml = `<span class="srow-chevron" aria-hidden="true">${disclosureIcon()}</span>`;
    } else if (row.kind === "empty") {
      rowClass += " srow-empty";
      chevronHtml = '<span class="srow-chevron srow-chevron-empty"></span>';
    } else {
      if (row.kind === "more") {
        rowClass += " srow-more";
      }
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

    var changeHtml = "";
    if (row.change === "added" || row.change === "removed" || row.change === "modified") {
      rowClass += ` srow-change-${row.change}`;
      if (row.change !== "modified") {
        changeHtml = `<span class="sr-only">${row.change === "added" ? "Added: " : "Removed: "}</span>`;
      }
    }

    var bodyHtml = "";
    if ((row.kind === "kv" || row.kind === "item") && typeof row.text === "string") {
      // A number JSON spells past what a double keeps, as the diff's answer gives it.
      bodyHtml = `<span class="tok-number">${escHtml(row.text)}</span>`;
    } else if (row.kind === "kv" || row.kind === "item") {
      var fv = pv.formatValue(row.value);
      bodyHtml = `<span class="${fv.colorClass}">${escHtml(fv.text)}</span>`;
    } else if (row.kind === "removed") {
      bodyHtml = '<span class="tok-meta">removed</span>';
    } else if (row.kind === "more") {
      // Chrome metadata, not content, as a preview's "(N more)" is.
      var changed = row.changed ? `, ${escHtml(row.changed)} changed` : "";
      bodyHtml = `<span class="tok-meta">… ${escHtml(row.hidden)} more${changed}</span>`;
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
      changeHtml +
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
    renderRowHtml: renderRowHtml,
    renderInlineTree: renderInlineTree,
    expansion: EXPANSION,
  };
})(typeof window !== "undefined" ? window : globalThis);
