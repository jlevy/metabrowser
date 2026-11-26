// Collection choices and index status around the shared Table view.
export {};

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser softschema plugin: SDK is unavailable");
}

/** @typedef {{id: string, label: string, count: number}} CollectionTable */
/** @typedef {{root: string, state: string, generation: string, complete: boolean, tables: CollectionTable[]}} CollectionAnswer */
/** @typedef {typeof import("../table/table-view.js").mountTable} MountTable */
/** @typedef {(host: HTMLElement, value: unknown, options: {virtualize: boolean}) => ({dispose?: () => void} | undefined)} RenderInlineTree */

const INDEX_POLL_MS = 350;
const REFRESH_POLL_MS = 3000;

mb.registerView("folder", "table", {
  render(container, ctx) {
    const path = ctx.path ?? "";
    const abort = new AbortController();
    /** @type {ReturnType<MountTable> | null} */
    let mounted = null;
    let shown = "";
    let generation = "";
    /** @type {ReturnType<typeof setTimeout> | undefined} */
    let timer;
    /** @type {CollectionAnswer | null} */
    let current = null;
    /** @type {MountTable | null} */
    let mount = null;
    /** @type {RenderInlineTree | null} */
    let inlineTree = null;
    let revision = 0;
    const status = document.createElement("p");
    status.className = "table-status";
    status.setAttribute("role", "status");
    const controls = document.createElement("div");
    controls.className = "table-toolbar";
    const content = document.createElement("div");
    content.className = "table-view";
    container.replaceChildren(controls, status, content);

    /** @param {{path: string, query: string}} target */
    function open(target) {
      void mb.navigation.open(target, { viewId: "table" }).then(() => show());
    }

    /** @param {string} id */
    function tableAddress(id) {
      return { path, query: id ? new URLSearchParams({ table: id }).toString() : "" };
    }

    /** @param {HTMLAnchorElement} link @param {{path: string, query: string}} target */
    function linkTo(link, target) {
      link.href = mb.navigation.href(target);
      link.addEventListener("click", (event) => {
        if (event.button || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) {
          return;
        }
        event.preventDefault();
        open(target);
      });
    }

    function list() {
      const table = document.createElement("table");
      table.className = "data-grid";
      const heading = table.createTHead().insertRow();
      for (const caption of ["Contract", "Records"]) {
        const th = document.createElement("th");
        th.scope = "col";
        th.textContent = caption;
        if (caption === "Records") {
          th.classList.add("data-num");
        }
        heading.append(th);
      }
      const body = table.createTBody();
      for (const item of current?.tables ?? []) {
        const row = body.insertRow();
        const link = document.createElement("a");
        link.textContent = item.label;
        linkTo(link, tableAddress(item.id));
        row.insertCell().append(link);
        const count = row.insertCell();
        count.className = "data-num";
        count.textContent = `${current?.complete ? "" : "≥"}${mb.formatInteger(item.count)}`;
      }
      content.replaceChildren(table);
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
      if (!selected) {
        revision += 1;
        mounted?.dispose();
        mounted = null;
        shown = "";
        controls.replaceChildren();
        if (view.tables.length) {
          list();
        } else {
          content.replaceChildren();
        }
        return;
      }
      if (mounted && shown === selected.id) {
        return;
      }
      const seq = ++revision;
      if (mount === null || inlineTree === null) {
        const [table, structured] = await Promise.all([
          /** @type {Promise<{mountTable: MountTable}>} */ (mb.plugins.load("table")),
          /** @type {Promise<{renderInlineTree: RenderInlineTree}>} */ (
            mb.plugins.load("structured")
          ),
        ]);
        mount = table.mountTable;
        inlineTree = structured.renderInlineTree;
      }
      if (seq !== revision || abort.signal.aborted) {
        return;
      }
      mounted?.dispose();
      const back = document.createElement("a");
      back.textContent = "Collection tables";
      linkTo(back, tableAddress(""));
      controls.replaceChildren(back);
      shown = selected.id;
      mounted = mount(content, {
        path,
        table: selected.id,
        collectionRoot: view.root,
        openCollectionAddress: open,
        renderJson: (host, value) => {
          const tree = document.createElement("div");
          tree.className = "structured-tree-mount";
          host.append(tree);
          return inlineTree?.(tree, value, { virtualize: false });
        },
      });
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
        status.textContent =
          answer.state === "indexing"
            ? "Indexing collection…"
            : answer.state === "failed"
              ? "The collection index could not be refreshed."
              : !answer.complete
                ? "The collection was only partly indexed."
                : !answer.tables.length
                  ? "No SoftSchema records in this folder."
                  : "";
        status.hidden = !status.textContent;
        if (generation && generation !== answer.generation) {
          void mounted?.refresh();
        }
        generation = answer.generation;
        await show();
        timer = setTimeout(
          () => void refresh(),
          answer.state === "indexing" ? INDEX_POLL_MS : REFRESH_POLL_MS,
        );
      } catch {
        if (abort.signal.aborted) {
          return;
        }
        status.hidden = false;
        status.textContent = "The collection could not be read.";
      }
    }

    const onPopState = () => void show();
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
