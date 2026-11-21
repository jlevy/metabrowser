// The SQLite Info view: fetch /api/plugin/sqlite/info, draw its model, dispose.
//
// What the view says is info-model.js's; this draws it with the shared primitives: a
// `.notice` for a state that is not Current or a read that failed, and each section as a
// `.data-grid` of labelled values. A view disposed before its answer arrives draws
// nothing from it.

import { infoModel } from "./info-model.js";

/**
 * @typedef {object} InfoSdk
 * @property {(plugin: string, route: string, params: Record<string, unknown>, options?: {signal?: AbortSignal}) => Promise<unknown>} fetchPluginData
 * @property {(value: number) => string} formatInteger
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

/**
 * Draw *model* into *root*.
 *
 * @param {HTMLElement} root
 * @param {import("./info-model.js").InfoModel} model
 */
export function drawInfo(root, model) {
  root.replaceChildren();
  for (const notice of model.notices) {
    const box = element("div", "notice sqlite-info-notice");
    box.dataset.severity = notice.severity;
    box.setAttribute("role", notice.severity === "error" ? "alert" : "status");
    box.append(element("strong", "sqlite-info-notice-title", notice.title));
    box.append(element("span", "sqlite-info-notice-text", notice.text));
    root.append(box);
  }
  for (const section of model.sections) {
    const block = element("section", "sqlite-info-section");
    block.append(element("h2", "data-label sqlite-info-heading", section.title));
    const table = element("table", "data-grid sqlite-info-table");
    const body = element("tbody");
    for (const row of section.rows) {
      const line = element("tr");
      const label = element("th", "sqlite-info-label", row.label);
      label.setAttribute("scope", "row");
      const classes = ["sqlite-info-value"];
      if (row.literal) {
        classes.push("data-literal");
      }
      if (row.numeric) {
        classes.push("sqlite-info-number");
      }
      if (row.muted) {
        classes.push("sqlite-info-muted");
      }
      line.append(label, element("td", classes.join(" "), row.value));
      body.append(line);
    }
    table.append(body);
    block.append(table);
    root.append(block);
  }
}

/**
 * Mount the Info view for the database at `ctx.path`.
 *
 * @param {HTMLElement} container
 * @param {{path?: string}} ctx
 * @param {InfoSdk} sdk
 * @returns {{dispose: () => void, ready: Promise<void>}}
 */
export function mountInfo(container, ctx, sdk) {
  const root = element("div", "sqlite-info");
  root.append(element("p", "sqlite-info-loading", "Reading this database…"));
  container.replaceChildren(root);
  const controller = new AbortController();
  let disposed = false;
  const format = { formatInteger: sdk.formatInteger };
  const ready = sdk
    .fetchPluginData("sqlite", "info", { path: ctx.path ?? "" }, { signal: controller.signal })
    .then(
      (payload) => {
        if (!disposed) {
          drawInfo(
            root,
            infoModel(/** @type {import("./info-model.js").InfoPayload} */ (payload), format),
          );
        }
      },
      (error) => {
        if (disposed) {
          return;
        }
        const payload = /** @type {{payload?: {error?: unknown}}} */ (error)?.payload;
        const message =
          typeof payload?.error === "string" ? payload.error : "Could not read this database.";
        drawInfo(root, infoModel({ error: { state: "unreadable", message } }, format));
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
