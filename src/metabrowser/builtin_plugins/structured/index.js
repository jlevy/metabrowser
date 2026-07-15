// Structured (JSON/YAML) built-in plugin.
//
// Owns kind "structured" (declared in manifest.toml for the three
// extensions .json / .yaml / .yml at priority 0). Two views:
//   ("structured", "tree")   — virtualized YAML-styled tree (default)
//   ("structured", "source") — raw text via mb.builtins.text.renderSource
//
// Exports the renderer + helpers at mb.builtins.structured so other
// plugins (agent-log per-event payloads, future schema-aware
// variants) can mount an inline tree without duplicating the logic.
// Consumers must read mb.builtins.structured AT RENDER TIME, never at
// script-load — see docs/plugins.md → "Render-time-only
// namespace rule".
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser structured plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  // preview.js + tree.js loaded before this file via manifest
  // [plugin].extra_scripts. They publish their helpers on globals.
  const preview = window.__structuredPreview;
  const tree = window.__structuredTree;
  if (!preview || !tree) {
    console.error("metabrowser structured plugin: preview.js / tree.js did not initialize");
    return;
  }
  const renderInlineTree = tree.renderInlineTree;

  // Track the currently mounted tree-view instance so dispose can
  // tear down its scroll listener when the preview pane is replaced.
  let _activeTreeHandle = null;

  // Reuse the text plugin's source renderer (syntax-highlighted raw
  // text). Looked up at render time so we don't depend on the text
  // plugin loading before structured. Used both for the explicit
  // Source view and as the fallback when a file can't be parsed.
  function renderSourceFallback(container, ctx) {
    if (mb.builtins?.text?.renderSource) {
      return mb.builtins.text.renderSource(container, ctx);
    }
    container.innerHTML =
      '<div class="preview-empty">Source view unavailable: text plugin not loaded.</div>';
  }

  function renderTree(container, ctx) {
    return mb.perf.measure("renderStructured:tree", async () => {
      let data;
      try {
        data = await mb.fetchPluginData("structured", "parsed", {
          path: ctx.path,
        });
      } catch (err) {
        // The fetch may resolve after the user has navigated away;
        // the shell detaches our container before mounting the next
        // file's pane. Writing to a detached node is harmless but
        // listeners we'd attach below would never get disposed.
        if (!container.isConnected) {
          return;
        }
        const message = err instanceof Error ? err.message : String(err);
        container.innerHTML = `<div class="preview-empty">Failed to load: ${mb.escapeHtml(message)}</div>`;
        return;
      }
      if (!container.isConnected) {
        return;
      }

      // A syntax error or an oversize file should never be a dead end:
      // silently fall back to the syntax-highlighted source view so the
      // file always renders as plain text rather than an error banner.
      if (data.parse_error || data.truncated) {
        return renderSourceFallback(container, ctx);
      }
      if (data.parsed === null || data.parsed === undefined) {
        container.innerHTML = '<div class="preview-empty">Empty or unparseable file.</div>';
        return;
      }

      // Wrap so the host's copy-as-YAML button frames the tree.
      // copyContent reads from a hidden <code> child; we stash the
      // canonical YAML there.
      const wrapper = window.document.createElement("div");
      wrapper.className = "content-copy-wrap";
      const copyBtn = window.document.createElement("button");
      copyBtn.className = "content-copy-btn";
      copyBtn.setAttribute("onclick", "copyContent(this)");
      copyBtn.setAttribute("title", "Copy as YAML");
      copyBtn.innerHTML = mb.icons.copy || "Copy";
      wrapper.appendChild(copyBtn);
      const copyPayload = window.document.createElement("code");
      copyPayload.style.display = "none";
      copyPayload.textContent = data.pretty_yaml || "";
      wrapper.appendChild(copyPayload);
      const treeMount = window.document.createElement("div");
      treeMount.className = "structured-tree-mount";
      wrapper.appendChild(treeMount);

      container.innerHTML = "";
      container.appendChild(wrapper);

      _activeTreeHandle = renderInlineTree(treeMount, data.parsed, {
        virtualize: true,
        // Auto-expand budget. The JsonViewer reference picked 8 for a
        // sidebar embed; the structured browser is a full pane. With
        // virtualization the DOM cost of a "row in expandedPaths"
        // bottoms out at zero (only visible rows are mounted), so the
        // budget is really a UX choice: how many lines of context
        // does the operator expect to see on first paint? 500 makes
        // the 16k-node MSFT bundle browseable without click-to-expand
        // on every nested object; the per-container threshold still
        // keeps individual 5000-item arrays collapsed by default.
        maxLines: 500,
        maxExpandThreshold: 200,
        indentChars: 2,
      });
    });
  }

  function disposeTree() {
    if (_activeTreeHandle && typeof _activeTreeHandle.dispose === "function") {
      _activeTreeHandle.dispose();
    }
    _activeTreeHandle = null;
  }

  // Namespace export — the stable embedding contract.
  if (!mb.builtins) {
    mb.builtins = {};
  }
  mb.builtins.structured = {
    renderSource: renderSourceFallback,
    renderTree: renderTree,
    renderInlineTree: renderInlineTree,
    materializeRows: tree.materializeRows,
    formatValue: preview.formatValue,
    generateStructuredPreview: preview.generateStructuredPreview,
    calculateOptimalExpansion: preview.calculateOptimalExpansion,
  };

  mb.registerView("structured", "tree", {
    render: renderTree,
    dispose: disposeTree,
  });
  mb.registerView("structured", "source", {
    render: renderSourceFallback,
  });
})();
