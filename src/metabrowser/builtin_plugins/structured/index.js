// Structured (JSON/YAML) built-in plugin.
//
// Owns kind "structured" (declared in manifest.toml for the three
// extensions .json / .yaml / .yml at priority 0). Three views:
//   ("structured", "tree")   — virtualized YAML-styled tree
//   ("structured", "table")  — ordered node table or record grid (default)
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

// The SDK loads the shared Tree library for this adapter and other embedding views.
const tree = await mb.loadStructuredTree();
const { renderInlineTree, expansion } = tree;

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
        '<div class="notice" data-severity="error" role="alert">Could not load structured data. Reload the page to try again.</div>';
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
export const formatValue = tree.formatValue;
export const generateStructuredPreview = tree.generateStructuredPreview;
export const calculateOptimalExpansion = tree.calculateOptimalExpansion;
export { expansion, renderInlineTree, renderSourceFallback as renderSource, renderTree };

// The Table view delegates qualifying roots to the shared record grid.

/**
 * @typedef {{
 *   mountTable: typeof import("../table/table-view.js").mountTable,
 * }} TableExports
 */

/** @type {Promise<TableExports> | null} */
let table = null;

// A record's value is at most TABLE_RECORD_VALUE_BYTES of JSON, and its tree is
// drawn whole, not virtualized. Its first draw opens a flat list whole: in headless
// Chrome a record holding a list of 12,750 integers (65,391 bytes of JSON, the
// largest the bound passes) drew 12,751 rows in 0.64 s, where a list of 50 took
// 0.03 s, and expanding it again after a collapse took 0.5 s (load average 2.5,
// 2026-11-20).
/** @param {HTMLElement} host @param {unknown} value */
export function renderRecordValue(host, value) {
  const mount = host.ownerDocument.createElement("div");
  mount.className = "structured-tree-mount";
  host.append(mount);
  return renderInlineTree(mount, value, { virtualize: false });
}

mb.registerView("structured", "table", {
  /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} ctx */
  async render(container, ctx) {
    const path = ctx.path ?? "";
    const revision = /** @type {{mtime_hash?: string} | undefined} */ (ctx.raw)?.mtime_hash;
    const pages = await mb.createStructuredPageReader(path, { revision });
    return mb.mountStructuredNodeTable(container, pages.table, {
      copyRow: pages.copyRow,
      async mountRecords(host, createRowCopy) {
        table ??= /** @type {Promise<TableExports>} */ (mb.plugins.load("table"));
        const { mountTable } = await table;
        return mountTable(host, {
          path,
          renderJson: renderRecordValue,
          rowAction: createRowCopy
            ? {
                label: "Copy record",
                render(_key, position) {
                  return position === null
                    ? null
                    : createRowCopy(`Copy record ${position}`, {
                        document: 0,
                        path: [position - 1],
                        offset: 0,
                      });
                },
              }
            : undefined,
        });
      },
    });
  },
});

mb.registerView("structured", "tree", {
  render: renderTree,
  dispose: disposeTree,
});
mb.registerView("structured", "source", {
  render: renderSourceFallback,
});
