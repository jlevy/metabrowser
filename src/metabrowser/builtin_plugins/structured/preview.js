// Structured plugin — pure value-classification + preview logic.
//
// Framework-independent value classification and preview logic. No React or
// Tailwind: emits CSS class names that map to the design tokens in
// styles.css (.tok-string, .tok-number, .tok-bool, .tok-null, .tok-key,
// .tok-punct, .tok-summary).
//
// Public surface (assigned to window.__structuredPreview so tree.js +
// index.js can read it after this script tag has loaded):
//   formatValue(value) -> {text, colorClass}
//   generateStructuredPreview(data, opts) -> {parts, hasMore}
//   calculateOptimalExpansion(data, opts) -> Set<pathStr>
//   calculateIndentStyle(level, indentChars) -> {paddingLeft}
//
// The functions are pure (no DOM, no fetch); unit-testable from the
// JSDOM shim by `vm.runInContext`-loading this file and probing
// __structuredPreview directly.
((global) => {
  // ── Value formatting ────────────────────────────────────────────

  function formatValue(value) {
    if (value === null) {
      return { text: "null", colorClass: "tok-null" };
    }
    if (value === undefined) {
      return { text: "undefined", colorClass: "tok-null" };
    }
    if (typeof value === "boolean") {
      return { text: value ? "true" : "false", colorClass: "tok-bool" };
    }
    if (typeof value === "number") {
      // JSON.stringify handles -0, NaN, Infinity better than String()
      // for our purposes (NaN/Infinity aren't valid JSON, but if a
      // YAML parser produced one we still want a stable display).
      if (Number.isNaN(value)) {
        return { text: "NaN", colorClass: "tok-number" };
      }
      if (!Number.isFinite(value)) {
        return { text: value > 0 ? "Infinity" : "-Infinity", colorClass: "tok-number" };
      }
      return { text: String(value), colorClass: "tok-number" };
    }
    if (typeof value === "string") {
      // Strings render with double quotes — YAML aesthetic
      // (defaultStringType: 'QUOTE_DOUBLE' in the reference).
      return { text: '"' + value + '"', colorClass: "tok-string" };
    }
    // Fallback for unexpected types (BigInt etc.). Stringify defensively.
    return { text: String(value), colorClass: "tok-string" };
  }

  // ── Indent ──────────────────────────────────────────────────────

  function calculateIndentStyle(level, indentChars) {
    // 1 em per indent step at the default size; indentChars=2 means
    // 1 em == 2 character widths in the monospace font we render in.
    var ic = indentChars || 2;
    return { paddingLeft: level * ic * 0.5 + "em" };
  }

  // ── Collapsed-node preview ─────────────────────────────────────
  //
  // Produces a parts array the renderer can stringify with stable
  // color classes. Each part is one of:
  //   {kind: "bracket", text}     — "{" / "}" / "[" / "]"
  //   {kind: "key", text}         — bare key (no quotes per YAML aesthetic)
  //   {kind: "punct", text}       — ":" / ", "
  //   {kind: "value", text, colorClass}   — primitive
  //   {kind: "nested", text}      — nested-container summary "{…}" / "[…]"
  //   {kind: "more", text}        — trailing "… (N more)" marker
  //
  // ``maxWidth`` is a soft budget in characters; once we exceed it we
  // emit a {kind: "more"} and stop. ``variant`` is reserved for
  // possible future "inline-tight" vs "inline-spread" styles; v1
  // ignores it and always emits the spread form.

  function _previewSummaryOf(value) {
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return { text: "[]", isEmpty: true };
      }
      return { text: "[…]", isEmpty: false };
    }
    if (value && typeof value === "object") {
      var keys = Object.keys(value);
      if (keys.length === 0) {
        return { text: "{}", isEmpty: true };
      }
      return { text: "{…}", isEmpty: false };
    }
    return null;
  }

  function generateStructuredPreview(data, opts) {
    opts = opts || {};
    var maxWidth = opts.maxWidth || 80;
    var parts = [];
    var width = 0;
    var hasMore = false;

    function pushPart(p) {
      parts.push(p);
      width += (p.text || "").length;
    }

    function fits(extra) {
      return width + extra <= maxWidth;
    }

    if (Array.isArray(data)) {
      pushPart({ kind: "bracket", text: "[" });
      for (var i = 0; i < data.length; i++) {
        var item = data[i];
        var nested = _previewSummaryOf(item);
        var piece;
        if (nested) {
          piece = { kind: "nested", text: nested.text };
        } else {
          var fv = formatValue(item);
          piece = { kind: "value", text: fv.text, colorClass: fv.colorClass };
        }
        if (i > 0) {
          if (!fits(2 + piece.text.length + 4)) {
            pushPart({ kind: "more", text: "… (" + (data.length - i) + " more)" });
            hasMore = true;
            break;
          }
          pushPart({ kind: "punct", text: ", " });
        } else if (!fits(piece.text.length + 4)) {
          pushPart({ kind: "more", text: "… (" + data.length + " more)" });
          hasMore = true;
          break;
        }
        pushPart(piece);
      }
      pushPart({ kind: "bracket", text: "]" });
      return { parts: parts, hasMore: hasMore };
    }

    if (data && typeof data === "object") {
      var keys = Object.keys(data);
      pushPart({ kind: "bracket", text: "{" });
      for (var k = 0; k < keys.length; k++) {
        var key = keys[k];
        var v = data[key];
        var fragLen = key.length + 2; // "key: "
        if (k > 0) {
          if (!fits(2 + fragLen + 4)) {
            pushPart({ kind: "more", text: "… (" + (keys.length - k) + " more)" });
            hasMore = true;
            break;
          }
          pushPart({ kind: "punct", text: ", " });
        } else if (!fits(fragLen + 4)) {
          pushPart({ kind: "more", text: "… (" + keys.length + " more)" });
          hasMore = true;
          break;
        }
        pushPart({ kind: "key", text: key });
        pushPart({ kind: "punct", text: ": " });
        var nested2 = _previewSummaryOf(v);
        if (nested2) {
          pushPart({ kind: "nested", text: nested2.text });
        } else {
          var fv2 = formatValue(v);
          pushPart({ kind: "value", text: fv2.text, colorClass: fv2.colorClass });
        }
      }
      pushPart({ kind: "bracket", text: "}" });
      return { parts: parts, hasMore: hasMore };
    }

    // Primitive at the root — unusual for a structured file but we
    // handle it for safety. Render as the bare value.
    var fv3 = formatValue(data);
    return {
      parts: [{ kind: "value", text: fv3.text, colorClass: fv3.colorClass }],
      hasMore: false,
    };
  }

  // ── Smart default expansion ────────────────────────────────────
  //
  // Walks the tree and returns a Set of path strings (JsonViewer-style
  // dot-and-bracket form, e.g. "$.bundle.summary.topDomains[0]") that
  // should be pre-expanded on first render.
  //
  // Heuristic:
  //   - Always expand "$" (root).
  //   - Greedily expand objects/arrays as long as the running row
  //     count stays under ``maxLines`` AND each expanded subtree has
  //     fewer than ``maxExpandThreshold`` direct children (so we
  //     never auto-expand a 5000-item array).
  //   - Children are walked breadth-first: top-level keys expand
  //     before second-level ones.

  function _isContainer(value) {
    return Array.isArray(value) || (value !== null && typeof value === "object");
  }

  function _countContainerChildren(value) {
    if (Array.isArray(value)) {
      return value.length;
    }
    if (value && typeof value === "object") {
      return Object.keys(value).length;
    }
    return 0;
  }

  function _childEntries(value, parentPath) {
    var entries = [];
    if (Array.isArray(value)) {
      for (var i = 0; i < value.length; i++) {
        entries.push({ path: parentPath + "[" + i + "]", value: value[i] });
      }
    } else if (value && typeof value === "object") {
      var keys = Object.keys(value);
      for (var k = 0; k < keys.length; k++) {
        entries.push({ path: parentPath + "." + keys[k], value: value[keys[k]] });
      }
    }
    return entries;
  }

  function calculateOptimalExpansion(data, opts) {
    opts = opts || {};
    var maxLines = opts.maxLines || 60;
    var maxExpandThreshold = opts.maxExpandThreshold || 80;

    var expanded = new Set();
    if (!_isContainer(data)) {
      return expanded;
    }

    // BFS queue: each entry is {path, value}. Each expanded container
    // contributes (childCount + 1) rows (children + close brace),
    // approximated as childCount. Root contributes 0 visible rows
    // itself; its children add up.
    var rowBudget = maxLines;
    expanded.add("$");
    rowBudget -= _countContainerChildren(data);

    var queue = _childEntries(data, "$");

    while (queue.length > 0 && rowBudget > 0) {
      var ent = queue.shift();
      if (!_isContainer(ent.value)) {
        continue;
      }
      var n = _countContainerChildren(ent.value);
      if (n === 0 || n > maxExpandThreshold) {
        continue;
      }
      if (n > rowBudget) {
        continue;
      }
      expanded.add(ent.path);
      rowBudget -= n;
      // Enqueue this container's children so deeper layers get a
      // chance to expand if budget remains.
      var children = _childEntries(ent.value, ent.path);
      for (var i = 0; i < children.length; i++) {
        queue.push(children[i]);
      }
    }
    return expanded;
  }

  global.__structuredPreview = {
    formatValue: formatValue,
    calculateIndentStyle: calculateIndentStyle,
    generateStructuredPreview: generateStructuredPreview,
    calculateOptimalExpansion: calculateOptimalExpansion,
  };
})(typeof window !== "undefined" ? window : globalThis);
