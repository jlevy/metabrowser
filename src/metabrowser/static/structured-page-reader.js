/** @typedef {import("./structured-node-table.js").Position} Position */
/** @typedef {import("./structured-node-table.js").Page & {format?: "json" | "yaml", source_text?: string, source_start_line?: number, tree_value?: unknown}} StructuredPage */

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
        throw Error("Tree is unavailable for this selection.", { cause: page.diagnostic });
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
