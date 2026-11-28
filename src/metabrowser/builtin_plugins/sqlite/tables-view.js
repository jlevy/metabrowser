// The SQLite Table and Schema views: fetch, draw the model, dispose.
//
// The Table view at a database's own address is its overview (`mountOverview`): its
// tables by group, each a link to its address, from the table plugin's tables route. At
// a table's address, `<database>/<segment>`, it is the table plugin's view of that table
// (`mountTable`), which this module loads on demand. The Schema view (`mountSchema`)
// draws each object's DDL. What each says is tables-model.js's.

import { overviewModel, schemaModel } from "./tables-model.js";

/**
 * @typedef {object} TablesSdk
 * @property {(plugin: string, route: string, params: Record<string, unknown>, options?: {signal?: AbortSignal}) => Promise<unknown>} fetchPluginData
 * @property {(value: number) => string} formatInteger
 * @property {{href: (target: {path: string}) => string, open: (target: {path: string}) => Promise<unknown>}} navigation
 * @property {{load: (name: string) => Promise<unknown>}} plugins
 *
 * @typedef {{dispose: () => void, ready: Promise<void>}} Mounted
 *
 * @typedef {{path?: string, raw?: unknown}} TablesContext
 */

/**
 * @param {string} tag
 * @param {string} [className]
 * @param {string} [text]
 */
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/** @param {HTMLElement} root @param {string} message */
function drawError(root, message) {
  const box = element("div", undefined, message);
  box.className = "notice sqlite-error";
  box.setAttribute("data-severity", "error");
  box.setAttribute("role", "alert");
  root.replaceChildren(box);
}

/**
 * A route's refusal in its own words, or *fallback*.
 *
 * @param {unknown} error
 * @param {string} fallback
 */
function refusal(error, fallback) {
  const payload = /** @type {{payload?: {error?: unknown}}} */ (error)?.payload;
  return typeof payload?.error === "string" ? payload.error : fallback;
}

/**
 * Fetch one answer into *root*, drawing it with *draw* unless the view was disposed
 * first, or the refusal with *fail*.
 *
 * @template Payload
 * @param {HTMLElement} container
 * @param {string} rootClass
 * @param {(signal: AbortSignal) => Promise<Payload>} fetch
 * @param {(root: HTMLElement, payload: Payload) => void} draw
 * @param {(root: HTMLElement, error: unknown) => void} fail
 * @returns {Mounted}
 */
function mountFetched(container, rootClass, fetch, draw, fail) {
  const root = element("div", rootClass);
  root.append(element("p", "sqlite-loading", "Reading this database…"));
  container.replaceChildren(root);
  const controller = new AbortController();
  let disposed = false;
  const ready = fetch(controller.signal).then(
    (payload) => {
      if (!disposed) {
        draw(root, payload);
      }
    },
    (error) => {
      if (!disposed) {
        fail(root, error);
      }
    },
  );
  return {
    ready,
    dispose() {
      disposed = true;
      controller.abort();
    },
  };
}

/**
 * Draw the overview *model* into *root*, its links opening through *sdk*.
 *
 * @param {HTMLElement} root
 * @param {import("./tables-model.js").OverviewModel} model
 * @param {TablesSdk} sdk
 * @param {typeof import("../table/table-catalog.js").renderTableCatalog} renderTableCatalog
 */
function drawOverview(root, model, sdk, renderTableCatalog) {
  if (model.empty) {
    root.replaceChildren(element("p", "sqlite-empty", model.empty));
    return;
  }
  renderTableCatalog(
    root,
    model.groups.map((group) => ({
      ...group,
      rows: group.rows.map((row) => ({
        ...row,
        note: row.note ?? undefined,
        href: sdk.navigation.href({ path: row.path }),
        open: () => sdk.navigation.open({ path: row.path }),
      })),
    })),
  );
}

/**
 * Mount the overview of the database at `ctx.path`.
 *
 * @param {HTMLElement} container
 * @param {TablesContext} ctx
 * @param {TablesSdk} sdk
 * @returns {Mounted}
 */
export function mountOverview(container, ctx, sdk) {
  return mountFetched(
    container,
    "sqlite-overview",
    (signal) =>
      Promise.all([
        sdk.fetchPluginData("table", "tables", { path: ctx.path ?? "" }, { signal }),
        /** @type {Promise<typeof import("../table/index.js")>} */ (sdk.plugins.load("table")),
      ]),
    (root, [payload, { renderTableCatalog }]) =>
      drawOverview(
        root,
        overviewModel(/** @type {import("./tables-model.js").TablesPayload} */ (payload), {
          formatInteger: sdk.formatInteger,
        }),
        sdk,
        renderTableCatalog,
      ),
    (root, error) => drawError(root, refusal(error, "Could not read this database.")),
  );
}

/**
 * Draw the Schema *model* into *root*.
 *
 * @param {HTMLElement} root
 * @param {import("./tables-model.js").SchemaModel} model
 */
export function drawSchema(root, model) {
  if (model.error) {
    drawError(root, model.error);
    return;
  }
  root.replaceChildren();
  for (const section of model.sections) {
    const block = element("section", "sqlite-schema-section");
    block.append(element("h2", "data-label sqlite-heading", section.title));
    for (const entry of section.entries) {
      const item = element("div", "sqlite-schema-entry");
      item.dataset.type = entry.type;
      item.append(element("pre", "data-literal sqlite-schema-sql", entry.sql));
      block.append(item);
    }
    if (section.foreignKeys.length) {
      const list = element("ul", "sqlite-schema-keys");
      for (const line of section.foreignKeys) {
        list.append(element("li", "data-literal", line));
      }
      block.append(element("h3", "data-label sqlite-subheading", "Foreign keys"), list);
    }
    root.append(block);
  }
}

/**
 * Mount the Schema view of the database or table at `ctx.path`, from *plugin*'s `schema`
 * route: this plugin's, or the fsqlite plugin's for a store's snapshot, which answers in
 * the same shape.
 *
 * @param {HTMLElement} container
 * @param {TablesContext} ctx
 * @param {TablesSdk} sdk
 * @param {string} [plugin]
 * @returns {Mounted}
 */
export function mountSchema(container, ctx, sdk, plugin = "sqlite") {
  return mountFetched(
    container,
    "sqlite-schema",
    (signal) => sdk.fetchPluginData(plugin, "schema", { path: ctx.path ?? "" }, { signal }),
    (root, payload) =>
      drawSchema(
        root,
        schemaModel(/** @type {import("./tables-model.js").SchemaPayload} */ (payload)),
      ),
    (root, error) =>
      drawSchema(
        root,
        schemaModel({
          error: { state: "unreadable", message: refusal(error, "Could not read this database.") },
        }),
      ),
  );
}

/**
 * The Table view: the overview at a database's address, the table plugin's view at a
 * table's.
 *
 * @param {HTMLElement} container
 * @param {TablesContext} ctx
 * @param {TablesSdk} sdk
 * @returns {Mounted | Promise<Mounted>}
 */
export function mountTableView(container, ctx, sdk) {
  const raw = /** @type {{container_inner?: unknown} | null | undefined} */ (ctx.raw);
  if (!raw?.container_inner) {
    return mountOverview(container, ctx, sdk);
  }
  return /** @type {Promise<{mountTable: typeof import("../table/table-view.js").mountTable}>} */ (
    sdk.plugins.load("table")
  ).then(({ mountTable }) => mountTable(container, { path: ctx.path ?? "" }));
}
