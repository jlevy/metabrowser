/** @typedef {import("./structured-node-table.js").Position} Position */
/** @typedef {ReturnType<typeof import("./structured-page-reader.js").createStructuredPageReader>} Pages */

/**
 * Mount the same views for a structured value embedded in another document.
 * The host supplies revision-pinned readers and owns the surrounding disclosure.
 * @param {HTMLElement} host
 * @param {MetabrowserPublicSdk} mb
 * @param {{
 *   label: string,
 *   ext: string,
 *   pages: () => Promise<Pages>,
 *   readTree?: (position: Position, signal: AbortSignal) => unknown,
 * }} options
 */
export function mountStructuredExcerpt(host, mb, options) {
  if (!mb.filterControls) {
    throw Error("Structured view controls are unavailable.");
  }
  const filterControls = mb.filterControls;
  const doc = host.ownerDocument;
  const controls = doc.createElement("div");
  const table = doc.createElement("div");
  const alternate = doc.createElement("div");
  host.replaceChildren(controls, table, alternate);
  const pages = options.pages();
  let disposed = false;
  /** @type {Position} */
  let selection = { document: 0, path: [], offset: 0 };
  /** @type {{dispose(): void} | undefined} */
  let tableHandle;
  /** @type {{dispose?: () => void} | undefined} */
  let treeHandle;
  /** @type {AbortController | undefined} */
  let drawing;
  const views = ["Table", "Tree", "Source"].map((label) => ({ label, value: label }));

  /** @param {string} mode */
  async function select(mode) {
    drawing?.abort();
    treeHandle?.dispose?.();
    treeHandle = undefined;
    const attempt = new AbortController();
    drawing = attempt;
    const restore = filterControls.keepFocus(controls);
    controls.innerHTML = filterControls.groupHtml({
      key: "structured-excerpt-view",
      label: options.label,
      select: "one",
      layout: "joined",
      options: views,
      value: mode,
    });
    restore();
    table.hidden = mode !== "Table";
    alternate.hidden = mode === "Table";
    alternate.replaceChildren();
    const position = selection;
    try {
      if (mode === "Table") {
        return;
      }
      if (mode === "Source") {
        const page = await (await pages).source(position, attempt.signal);
        if (attempt.signal.aborted) {
          return;
        }
        if (typeof page.source_text !== "string") {
          throw Error(page.diagnostic || "Source is unavailable for this selection.");
        }
        mb.renderSourceView(
          alternate,
          { content: page.source_text, ext: page.format === "json" ? ".json" : options.ext },
          { lineStart: page.source_start_line, signal: attempt.signal },
        );
        return;
      }
      const [structured, value] = await Promise.all([
        mb.loadStructuredTree(),
        options.readTree
          ? options.readTree(position, attempt.signal)
          : pages.then((reader) => reader.tree(position, attempt.signal)),
      ]);
      if (attempt.signal.aborted) {
        return;
      }
      const mount = doc.createElement("div");
      mount.className = "structured-tree-mount";
      alternate.append(mount);
      treeHandle = structured.renderInlineTree(mount, value, { virtualize: true });
    } catch (error) {
      if (!attempt.signal.aborted) {
        showNotice(alternate, error);
      }
    }
  }

  /** @param {HTMLElement} element @param {unknown} error */
  function showNotice(element, error) {
    const warning = doc.createElement("div");
    warning.className = "notice";
    warning.dataset.severity = "warning";
    warning.setAttribute("role", "status");
    warning.textContent = error instanceof Error ? error.message : String(error);
    element.replaceChildren(warning);
  }
  const unbind = filterControls.bind(controls, {
    onChange(_key, mode) {
      void select(mode);
    },
  });
  void select("Table");
  void pages
    .then(({ table: readTable, copyRow }) =>
      disposed
        ? undefined
        : mb.mountStructuredNodeTable(table, readTable, {
            copyRow,
            onSelect(position) {
              selection = position;
            },
          }),
    )
    .then((handle) => {
      if (disposed) {
        handle?.dispose();
      } else {
        tableHandle = handle;
      }
    })
    .catch((error) => {
      if (!disposed) {
        showNotice(table, error);
      }
    });
  return {
    dispose() {
      disposed = true;
      unbind();
      drawing?.abort();
      treeHandle?.dispose?.();
      tableHandle?.dispose();
      host.replaceChildren();
    },
  };
}
