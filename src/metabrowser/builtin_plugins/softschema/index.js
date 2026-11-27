// Collection choices and index status around the shared Table view.
export {};

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser softschema plugin: SDK is unavailable");
}

/** @typedef {{id: string, label: string, count: number}} CollectionTable */
/** @typedef {{root: string, state: string, generation: string, complete: boolean, paths_checked: number, summary: object | null, tables: CollectionTable[]}} CollectionAnswer */
/** @typedef {typeof import("../table/index.js")} TableExports */
/** @typedef {(host: HTMLElement, value: unknown) => ({dispose?: () => void} | undefined)} RenderRecordValue */

const INDEXING = "Indexing collection…";
const INDEX_POLL_MS = 350;
const REFRESH_POLL_MS = 3000;

mb.registerView("folder", "table", {
  render(container, ctx) {
    const path = ctx.path ?? "";
    const abort = new AbortController();
    /** @type {ReturnType<TableExports["mountTable"]> | null} */
    let mounted = null;
    let shown = "";
    let generation = "";
    /** @type {ReturnType<typeof setTimeout> | undefined} */
    let timer;
    /** @type {CollectionAnswer | null} */
    let current = null;
    /** @type {Promise<TableExports> | null} */
    let tableAssets = null;
    /** @type {RenderRecordValue | null} */
    let renderRecordValue = null;
    /** @type {string | null} */
    let catalogGeneration = null;
    let revision = 0;
    const progress = document.createElement("div");
    progress.className = "mb-delayed-loading";
    mb.renderIndexProgress(progress, INDEXING);
    const status = document.createElement("p");
    status.className = "table-status";
    status.setAttribute("role", "status");
    status.hidden = true;
    const content = document.createElement("div");
    content.className = "table-view-mount";
    container.replaceChildren(progress, status, content);

    /** @param {{path: string, query: string}} target */
    function open(target) {
      void mb.navigation.open(target, { viewId: "table" }).then(show).catch(showFailure);
    }

    /** @param {string} id */
    function tableAddress(id) {
      return { path, query: new URLSearchParams({ table: id }).toString() };
    }

    function loadTable() {
      tableAssets ??= /** @type {Promise<TableExports>} */ (mb.plugins.load("table"));
      return tableAssets;
    }

    /** @param {CollectionAnswer} view @param {TableExports["renderTableCatalog"]} renderTableCatalog */
    function list(view, renderTableCatalog) {
      renderTableCatalog(content, [
        {
          title: "Tables",
          rows: view.tables.map((item) => {
            const target = tableAddress(item.id);
            const count = `${view.complete ? "" : "≥"}${mb.formatInteger(item.count)}`;
            return {
              label: item.label,
              estimate: `${count} ${item.count === 1 && view.complete ? "record" : "records"}`,
              href: mb.navigation.href(target),
              open: () => open(target),
            };
          }),
        },
      ]);
    }

    async function show() {
      const view = current;
      const address = mb.navigation.current();
      if (
        !view ||
        !address ||
        address.path.replace(/\/$/, "") !== path.replace(/\/$/, "") ||
        abort.signal.aborted
      ) {
        return;
      }
      const table = new URLSearchParams(address.query).get("table");
      const selected = view.tables.find((item) => item.id === table);
      const seq = ++revision;
      if (mounted && selected && shown === selected.id) {
        return;
      }
      if (!selected && !mounted && catalogGeneration === view.generation) {
        return;
      }
      if (!selected) {
        mounted?.dispose();
        mounted = null;
        shown = "";
        if (view.tables.length) {
          const { renderTableCatalog } = await loadTable();
          if (seq !== revision || abort.signal.aborted) {
            return;
          }
          list(view, renderTableCatalog);
        } else {
          content.replaceChildren();
        }
        catalogGeneration = view.generation;
        return;
      }
      const tablePromise = loadTable();
      if (renderRecordValue === null) {
        const [, structured] = await Promise.all([tablePromise, mb.plugins.load("structured")]);
        renderRecordValue = structured.renderRecordValue;
      }
      const { mountTable } = await tablePromise;
      if (seq !== revision || abort.signal.aborted) {
        return;
      }
      mounted?.dispose();
      catalogGeneration = null;
      shown = selected.id;
      mounted = mountTable(content, {
        path,
        table: selected.id,
        collectionRoot: view.root,
        catalogAddress: tableAddress(""),
        openCollectionAddress: open,
        renderJson: renderRecordValue,
      });
    }

    /** @param {string} message @param {"warning" | "error"} [severity] */
    function setStatus(message, severity) {
      if (status.textContent !== message) {
        status.textContent = message;
      }
      status.classList.toggle("notice", severity !== undefined);
      if (severity) {
        status.dataset.severity = severity;
      } else {
        delete status.dataset.severity;
      }
      status.hidden = !message;
    }

    function showFailure() {
      if (!abort.signal.aborted) {
        progress.hidden = true;
        setStatus("The collection could not be read.", "error");
      }
    }

    async function refresh() {
      try {
        const answer = /** @type {CollectionAnswer} */ (
          /** @type {unknown} */ (
            await mb.fetchPluginData("softschema", "collection", { path }, { signal: abort.signal })
          )
        );
        if (abort.signal.aborted) {
          return;
        }
        current = answer;
        const cold = answer.state === "indexing" && answer.summary === null;
        progress.hidden = !cold;
        if (answer.state === "failed") {
          setStatus("The collection index could not be refreshed.", "error");
        } else if (cold) {
          const checked = answer.paths_checked;
          const paths = checked === 1 ? "path" : "paths";
          mb.renderIndexProgress(
            progress,
            checked > 0 ? `${INDEXING} ${mb.formatInteger(checked)} ${paths} checked` : INDEXING,
          );
          setStatus("");
        } else if (!answer.complete) {
          setStatus("The collection was only partly indexed.", "warning");
        } else {
          setStatus(answer.tables.length ? "" : "No SoftSchema records in this folder.");
        }
        const previousMount = mounted;
        await show();
        if (generation && generation !== answer.generation && mounted === previousMount) {
          await mounted?.refresh({ generation: answer.generation });
        }
        if (abort.signal.aborted) {
          return;
        }
        generation = answer.generation;
        timer = setTimeout(
          () => void refresh(),
          answer.state === "indexing" ? INDEX_POLL_MS : REFRESH_POLL_MS,
        );
      } catch {
        showFailure();
      }
    }

    const onPopState = () => void show().catch(showFailure);
    window.addEventListener("popstate", onPopState);
    void refresh();
    return {
      dispose() {
        abort.abort();
        revision += 1;
        clearTimeout(timer);
        window.removeEventListener("popstate", onPopState);
        mounted?.dispose();
      },
    };
  },
});
