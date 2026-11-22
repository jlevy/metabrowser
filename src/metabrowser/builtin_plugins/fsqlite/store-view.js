// The fsqlite store's Info view: fetch /api/plugin/fsqlite/info, draw its model, dispose.
//
// What the view says is store-model.js's; the snapshot's sections and the drawing are
// the SQLite plugin's (`infoModel` and `drawInfo`, from its exports through
// `mb.plugins.load("sqlite")`, which `requires` in manifest.toml declares), so a store's
// Info reads as a database's does with the store's own section above it. A view disposed
// before its answer arrives draws nothing from it.

import { storeModel } from "./store-model.js";

/**
 * @typedef {object} SqliteExports
 * @property {typeof import("../sqlite/info-model.js").infoModel} infoModel
 * @property {typeof import("../sqlite/info-view.js").drawInfo} drawInfo
 *
 * @typedef {object} StoreSdk
 * @property {(plugin: string, route: string, params: Record<string, unknown>, options?: {signal?: AbortSignal}) => Promise<unknown>} fetchPluginData
 * @property {(value: number) => string} formatInteger
 * @property {{load: (name: string) => Promise<unknown>}} plugins
 */

/**
 * Mount the Info view for the store whose marker is at `ctx.path`.
 *
 * @param {HTMLElement} container
 * @param {{path?: string}} ctx
 * @param {StoreSdk} sdk
 * @returns {{dispose: () => void, ready: Promise<void>}}
 */
export function mountStoreInfo(container, ctx, sdk) {
  const root = document.createElement("div");
  root.className = "sqlite-info";
  const loading = document.createElement("p");
  loading.className = "sqlite-info-loading";
  loading.textContent = "Reading this store…";
  root.append(loading);
  container.replaceChildren(root);
  const controller = new AbortController();
  let disposed = false;
  const format = { formatInteger: sdk.formatInteger };
  const sqlite = /** @type {Promise<SqliteExports>} */ (sdk.plugins.load("sqlite"));
  const answer = sdk
    .fetchPluginData("fsqlite", "info", { path: ctx.path ?? "" }, { signal: controller.signal })
    .then(
      (payload) => /** @type {import("./store-model.js").StorePayload} */ (payload),
      (error) => {
        const payload = /** @type {{payload?: {error?: unknown}}} */ (error)?.payload;
        const message =
          typeof payload?.error === "string" ? payload.error : "Could not read this store.";
        return /** @type {import("./store-model.js").StorePayload} */ ({
          error: { state: "unreadable", message },
        });
      },
    );
  const ready = Promise.all([sqlite, answer]).then(
    ([{ infoModel, drawInfo }, payload]) => {
      if (!disposed) {
        drawInfo(root, storeModel(payload, format, infoModel));
      }
    },
    () => {
      if (!disposed) {
        loading.textContent = "Could not load the SQLite plugin this view draws with.";
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
