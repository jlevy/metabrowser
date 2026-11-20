// Structured (JSON/YAML) built-in plugin.
//
// Owns kind "structured" (declared in manifest.toml for the three
// extensions .json / .yaml / .yml at priority 0). Two views:
//   ("structured", "tree")   — virtualized YAML-styled tree (default)
//   ("structured", "source") — raw text via mb.renderSourceView
//
// Exports the renderer + helpers from this module so other plugins
// (agent-log per-event payloads, a rendered diff's trees) can mount a
// tree without duplicating the logic: a plugin that declares
// `requires = ["structured"]` reads them with
// `await mb.plugins.load("structured")` (docs/plugins.md,
// "Declared Dependencies").
const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser structured plugin: window.metabrowser missing — SDK not loaded");
}

// preview.js + tree.js loaded before this file via manifest
// [plugin].extra_scripts. They publish their helpers on globals.
const preview = window.__structuredPreview;
const tree = window.__structuredTree;
if (!preview || !tree) {
  throw new Error("metabrowser structured plugin: preview.js / tree.js did not initialize");
}
const renderInlineTree = tree.renderInlineTree;
// tree.js's `expansion` says why the file view opens what it opens; a rendered diff
// reads it too.
const expansion = tree.expansion;

// Track the currently mounted tree-view instance so dispose can
// tear down its scroll listener when the preview pane is replaced.
let _activeTreeHandle = null;

// Use the host's generic Source renderer rather than depending on another
// kind's lazily loaded plugin. Used both for the explicit Source view and as
// the fallback when a file cannot be parsed.
function renderSourceFallback(container, ctx) {
  const raw =
    ctx.raw && typeof ctx.raw === "object"
      ? /** @type {Record<string, unknown> & {content?: string, ext?: string}} */ (ctx.raw)
      : {};
  mb.perf.measure("renderStructured:source", () => {
    mb.renderSourceView(container, raw);
  });
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
      console.warn("structured data load failed", err);
      container.innerHTML =
        '<div class="notice" data-severity="error" role="alert">Could not load structured data. Refresh the page to try again.</div>';
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
    // Wrap so the host's copy-as-YAML button frames the tree.
    // The copy delegate reads a hidden <code> child; we stash the
    // canonical YAML there.
    const wrapper = window.document.createElement("div");
    wrapper.className = "content-copy-wrap";
    const copyBtn = window.document.createElement("button");
    copyBtn.className = "icon-btn icon-btn-reveal icon-btn-overlay content-copy-btn";
    copyBtn.type = "button";
    // The SDK's delegated copy listener runs it; it reads the hidden <code> below.
    copyBtn.setAttribute("data-mb-copy", "wrap");
    mb.ownDelegate(copyBtn);
    copyBtn.setAttribute("data-tip-text", "Copy as YAML");
    copyBtn.setAttribute("aria-label", "Copy as YAML");
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
      ...expansion,
    });
  });
}

function disposeTree() {
  if (_activeTreeHandle && typeof _activeTreeHandle.dispose === "function") {
    _activeTreeHandle.dispose();
  }
  _activeTreeHandle = null;
}

// The stable embedding contract: what a plugin that requires this one gets from
// `mb.plugins.load("structured")`.
export const materializeRows = tree.materializeRows;
export const renderRowHtml = tree.renderRowHtml;
export const formatValue = preview.formatValue;
export const generateStructuredPreview = preview.generateStructuredPreview;
export const calculateOptimalExpansion = preview.calculateOptimalExpansion;
export { expansion, renderInlineTree, renderSourceFallback as renderSource, renderTree };

mb.registerView("structured", "tree", {
  render: renderTree,
  dispose: disposeTree,
});
mb.registerView("structured", "source", {
  render: renderSourceFallback,
});
