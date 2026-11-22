// The fsqlite store's Table and Schema views, drawn by the SQLite plugin's.
//
// A store's tables are its snapshot's, each at `<marker>/<segment>` as a database's are
// at `<database>/<segment>`, and the table plugin's routes serve them through this
// plugin's `[[table_source]]`. So the Table view is the SQLite plugin's `mountTableView`
// as it stands: the store's overview at the marker's address, from
// /api/plugin/table/tables, and the table plugin's view at a table's. The Schema view is
// its `mountSchema` over /api/plugin/fsqlite/schema, which answers as
// /api/plugin/sqlite/schema does. Both arrive through the SQLite plugin's exports
// (`mb.plugins.load("sqlite")`, which `requires` in manifest.toml declares).
//
// The returned handle is ready when the drawn view is, and disposes it, or, when the
// view is disposed before the SQLite plugin has loaded, mounts nothing.

/**
 * @typedef {object} SqliteExports
 * @property {typeof import("../sqlite/tables-view.js").mountTableView} mountTableView
 * @property {typeof import("../sqlite/tables-view.js").mountSchema} mountSchema
 *
 * @typedef {import("../sqlite/tables-view.js").TablesSdk} StoreTablesSdk
 * @typedef {import("../sqlite/tables-view.js").TablesContext} StoreTablesContext
 * @typedef {{dispose: () => void, ready: Promise<void>}} Mounted
 */

/**
 * Mount what *mount* draws with the SQLite plugin's exports into *container*.
 *
 * @param {HTMLElement} container
 * @param {StoreTablesSdk} sdk
 * @param {(sqlite: SqliteExports) => Mounted | Promise<Mounted>} mount
 * @returns {Mounted}
 */
function withSqlite(container, sdk, mount) {
  /** @type {Mounted | null} */
  let inner = null;
  let disposed = false;
  const ready = /** @type {Promise<SqliteExports>} */ (sdk.plugins.load("sqlite")).then(
    async (sqlite) => {
      if (disposed) {
        return;
      }
      const mounted = await mount(sqlite);
      if (disposed) {
        mounted.dispose();
        return;
      }
      inner = mounted;
      await mounted.ready;
    },
    () => {
      if (!disposed) {
        const notice = document.createElement("p");
        notice.className = "notice sqlite-error";
        notice.textContent = "Could not load the SQLite plugin this view draws with.";
        container.replaceChildren(notice);
      }
    },
  );
  return {
    ready,
    dispose() {
      disposed = true;
      inner?.dispose();
    },
  };
}

/**
 * Mount the Table view for the store or table at `ctx.path`.
 *
 * @param {HTMLElement} container
 * @param {StoreTablesContext} ctx
 * @param {StoreTablesSdk} sdk
 * @returns {Mounted}
 */
export function mountStoreTable(container, ctx, sdk) {
  return withSqlite(container, sdk, ({ mountTableView }) => mountTableView(container, ctx, sdk));
}

/**
 * Mount the Schema view for the store or table at `ctx.path`.
 *
 * @param {HTMLElement} container
 * @param {StoreTablesContext} ctx
 * @param {StoreTablesSdk} sdk
 * @returns {Mounted}
 */
export function mountStoreSchema(container, ctx, sdk) {
  return withSqlite(container, sdk, ({ mountSchema }) =>
    mountSchema(container, ctx, sdk, "fsqlite"),
  );
}
