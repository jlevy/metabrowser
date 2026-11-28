/** @typedef {import("./structured-node-table.js").Position} Position */
/** @typedef {import("./structured-node-table.js").Page & {format?: "json" | "yaml", source_text?: string, source_start_line?: number, tree_value?: unknown}} StructuredPage */

/** @param {unknown} reason @param {string} view */
export function structuredFailure(reason, view) {
  const status = reason && typeof reason === "object" && "status" in reason ? reason.status : null;
  const detail =
    reason && typeof reason === "object" && "diagnostic" in reason ? reason.diagnostic : null;
  if (status === 409 || status === "changed") {
    return "The file changed after this view was opened.";
  }
  if (status === 403) {
    return "Access to this file was denied.";
  }
  if (status === 404) {
    return "The file is unavailable.";
  }
  if (status === "missing") {
    return "The selected value is unavailable.";
  }
  if (status === "too_large" || status === 413) {
    return detail === "Projection exceeds its node or depth budget"
      ? `This value exceeds the ${view} view’s size or nesting limit.`
      : `This file exceeds the ${view} view’s parsing limit.`;
  }
  if (status === "invalid") {
    return typeof detail === "string" && detail
      ? detail
      : "The structured data could not be parsed.";
  }
  if (status === 400 || status === "bad_request") {
    return "The requested selection is invalid.";
  }
  return `The ${view} view could not be loaded.`;
}

/** @param {HTMLElement} host @param {string} message @param {(() => void) | undefined} openSource
 * @param {string} [label] @param {"warning" | "info"} [severity] */
export function showStructuredNotice(
  host,
  message,
  openSource,
  label = "Open Source",
  severity = "warning",
) {
  const doc = host.ownerDocument;
  const notice = doc.createElement("div");
  notice.className = "notice";
  notice.dataset.severity = severity;
  notice.setAttribute("role", "status");
  notice.textContent = message;
  if (openSource) {
    const action = doc.createElement("button");
    action.type = "button";
    action.className = "btn";
    action.textContent = label;
    action.addEventListener("click", openSource);
    notice.append(" ", action);
  }
  host.replaceChildren(notice);
}

/**
 * Keep each view of a structured file pinned to the same revision, including
 * reads issued after a disclosure is expanded or an individual row is copied.
 * @param {MetabrowserPublicSdk["fetchPluginData"]} fetchPluginData
 * @param {string} path
 * @param {{frontmatter?: boolean, fenceLine?: number, revision?: string}} [options]
 */
export function createStructuredPageReader(fetchPluginData, path, options = {}) {
  let revision = options.revision;

  /**
   * @param {Position} position
   * @param {AbortSignal} signal
   * @param {{depth?: number, source?: 1, tree?: 1, copy?: "row"}} query
   */
  async function read(position, signal, query) {
    const page = /** @type {StructuredPage & Record<string, unknown>} */ (
      await fetchPluginData(
        "structured",
        "parsed",
        {
          path,
          projection: "nodes",
          frontmatter: options.frontmatter ? 1 : undefined,
          fence_line: options.fenceLine,
          mtime_hash: revision,
          document: position.document,
          node: JSON.stringify(position.path),
          offset: position.offset,
          ...query,
        },
        { signal },
      )
    );
    revision ??= page.mtime_hash;
    return page;
  }

  return {
    /** @type {import("./structured-node-table.js").ReadPage} */
    table: (position, signal, depth) => read(position, signal, { depth }),
    /** @param {Position} position @param {AbortSignal} signal */
    source: (position, signal) => read(position, signal, { source: 1 }),
    /** @param {Position} position @param {AbortSignal} signal */
    async tree(position, signal) {
      const page = await read(position, signal, { tree: 1 });
      if (!Object.hasOwn(page, "tree_value")) {
        throw Object.assign(new Error("Tree is unavailable for this selection."), {
          status: page.status,
          diagnostic: page.diagnostic,
        });
      }
      return page.tree_value;
    },
    /** @param {Position} position @param {AbortSignal} signal */
    async copyRow(position, signal) {
      const page = await read(position, signal, { copy: "row" });
      if (typeof page.copy_text !== "string") {
        throw Error("Copy is unavailable for this row.", { cause: page.diagnostic });
      }
      return page.copy_text;
    },
  };
}
