// The fsqlite store's Info view model: what the view says about one answer of
// /api/plugin/fsqlite/info, as sections of labelled values and notices.
//
// Pure: no DOM and no SDK. The store's own section comes first: its format, identity,
// the version `current` names and its snapshot, and the transaction envelopes waiting for
// the next reconcile. The snapshot's sections follow, from the SQLite plugin's Info model
// (sqlite/info-model.js), which the view passes in from that plugin's exports. The
// browserless session (tests/dom/fsqlite-info-session.js) prints the model for every state
// the route answers, so what the page says about a store is pinned by a golden.

/**
 * @typedef {import("../sqlite/info-model.js").InfoPayload} InfoPayload
 * @typedef {import("../sqlite/info-model.js").InfoModel} InfoModel
 * @typedef {import("../sqlite/info-model.js").InfoRow} InfoRow
 * @typedef {import("../sqlite/info-model.js").InfoNotice} InfoNotice
 * @typedef {import("../sqlite/info-model.js").FormatInteger} FormatInteger
 * @typedef {(payload: InfoPayload, format: {formatInteger: FormatInteger}) => InfoModel} SnapshotModel
 *
 * @typedef {object} StorePending
 * @property {number} committed
 * @property {number} uncommitted
 * @property {boolean} complete
 *
 * @typedef {object} StoreFacts
 * @property {string} [format_version]
 * @property {string} [store_id]
 * @property {string[]} [required_features]
 * @property {number} [version]
 * @property {string} [snapshot]
 * @property {number} [attempts]
 * @property {StorePending} [pending]
 *
 * @typedef {object} StorePayload
 * @property {string} [path]
 * @property {string | null} [generation]
 * @property {StoreFacts} [store]
 * @property {InfoPayload} [snapshot]
 * @property {{state: string, message: string}} [error]
 */

/** What each store state is called (the fsqlite format's validation states). */
/** @type {Record<string, string>} */
export const STORE_STATES = {
  invalid: "Not a valid store",
  unsupported: "Unsupported store",
  corrupt: "Corrupt store",
};

/**
 * @param {number} count
 * @param {string} one
 * @param {string} many
 * @param {FormatInteger} formatInteger
 */
function counted(count, one, many, formatInteger) {
  return `${formatInteger(count)} ${count === 1 ? one : many}`;
}

/**
 * The Pending row's text: committed envelopes wait for the next reconcile, and
 * uncommitted ones are captures in flight or torn.
 *
 * @param {StorePending} pending
 * @param {FormatInteger} formatInteger
 */
export function pendingText(pending, formatInteger) {
  const prefix = pending.complete ? "" : "at least ";
  if (pending.committed === 0 && pending.uncommitted === 0) {
    return pending.complete ? "None" : "Not counted: too many entries";
  }
  const parts = [];
  if (pending.committed > 0) {
    parts.push(
      `${prefix}${counted(pending.committed, "committed envelope", "committed envelopes", formatInteger)} waiting for the next reconcile`,
    );
  }
  if (pending.uncommitted > 0) {
    parts.push(
      `${prefix}${counted(pending.uncommitted, "uncommitted envelope", "uncommitted envelopes", formatInteger)}, in flight or torn`,
    );
  }
  return parts.join("; ");
}

/**
 * The view's model of one answer: the store's section, then the snapshot's.
 *
 * @param {StorePayload} payload
 * @param {{formatInteger: FormatInteger}} format
 * @param {SnapshotModel} snapshotModel The SQLite plugin's `infoModel`.
 * @returns {InfoModel}
 */
export function storeModel(payload, format, snapshotModel) {
  const { formatInteger } = format;
  /** @type {InfoNotice[]} */
  const notices = [];
  if (payload.error) {
    notices.push({
      severity: "error",
      title: STORE_STATES[payload.error.state] ?? "Unreadable store",
      text: payload.error.message,
    });
  }
  const store = payload.store ?? {};
  /** @type {InfoRow[]} */
  const rows = [];
  if (store.format_version !== undefined) {
    rows.push({ label: "Format", value: `fsqlite ${store.format_version}`, literal: true });
  }
  if (store.store_id !== undefined) {
    rows.push({ label: "Store", value: store.store_id, literal: true });
  }
  if (store.required_features && store.required_features.length > 0) {
    rows.push({ label: "Requires", value: store.required_features.join(", "), literal: true });
  }
  if (store.version !== undefined) {
    rows.push({ label: "Version", value: formatInteger(store.version), numeric: true });
  }
  if (store.snapshot !== undefined) {
    rows.push({ label: "Snapshot", value: `snapshots/${store.snapshot}`, literal: true });
  }
  if ((store.attempts ?? 1) > 1) {
    rows.push({
      label: "Pointer",
      value: "Read again: the snapshot it first named was collected",
      muted: true,
    });
  }
  if (store.pending) {
    const none = store.pending.committed === 0 && store.pending.uncommitted === 0;
    rows.push({
      label: "Pending",
      value: pendingText(store.pending, formatInteger),
      muted: none && store.pending.complete,
    });
  }
  const sections = rows.length ? [{ title: "Store", rows }] : [];
  if (payload.snapshot) {
    const snapshot = snapshotModel(payload.snapshot, format);
    notices.push(...snapshot.notices);
    sections.push(...snapshot.sections);
  }
  return { notices, sections };
}
