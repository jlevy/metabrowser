// The SQLite Info view's model: what the view says about one answer of
// /api/plugin/sqlite/info, as sections of labelled values and at most one notice.
//
// Pure: no DOM and no SDK. The view draws it (info-view.js), and the browserless session
// (tests/dom/sqlite-info-session.js) prints it for every state the route answers, so what
// the page says about a database is pinned by a golden.

/**
 * @typedef {object} InfoAccess
 * @property {string} mode
 * @property {string} state
 * @property {string} reason
 * @property {number} attempts
 * @property {string[]} notices
 *
 * @typedef {object} InfoSidecar
 * @property {string} name
 * @property {number} size
 * @property {boolean} [live]
 * @property {number} [frames]
 *
 * @typedef {object} InfoDatabase
 * @property {number} page_size
 * @property {number} page_count
 * @property {string} encoding
 * @property {number} user_version
 * @property {number} application_id
 * @property {string | null} application_name
 * @property {number} freelist_count
 * @property {Record<string, number>} objects
 *
 * @typedef {object} InfoLibraryVersion
 * @property {string} version
 * @property {string} meaning
 * @property {boolean} available
 *
 * @typedef {object} InfoLibrary
 * @property {string} version
 * @property {string} minimum
 * @property {boolean} meets_minimum
 * @property {InfoLibraryVersion[]} versions
 *
 * @typedef {object} InfoPayload
 * @property {string} [path]
 * @property {InfoAccess} [access]
 * @property {string} [journal_mode]
 * @property {number} [links]
 * @property {number} [size]
 * @property {InfoSidecar[]} [sidecars]
 * @property {InfoDatabase} [database]
 * @property {InfoLibrary} [library]
 * @property {{state: string, message: string}} [error]
 *
 * @typedef {object} InfoRow
 * @property {string} label
 * @property {string} value
 * @property {boolean} [literal] A literal value (a version, hex), drawn monospaced.
 * @property {boolean} [numeric] A number, drawn in tabular numerals.
 * @property {boolean} [muted]
 *
 * @typedef {object} InfoSection
 * @property {string} title
 * @property {InfoRow[]} rows
 *
 * @typedef {object} InfoNotice
 * @property {"warning" | "error"} severity
 * @property {string} title
 * @property {string} text
 *
 * @typedef {object} InfoModel
 * @property {InfoNotice[]} notices
 * @property {InfoSection[]} sections
 *
 * @typedef {(value: number) => string} FormatInteger
 */

/** What each state is called, and whether it is a warning or an error. */
/** @type {Record<string, {title: string, severity: "warning" | "error"}>} */
export const STATES = {
  current: { title: "Current", severity: "warning" },
  another_name: { title: "Another name", severity: "warning" },
  without_log: { title: "Without its log", severity: "warning" },
  writer_busy: { title: "Writer busy", severity: "warning" },
  changing: { title: "Changing", severity: "warning" },
  busy: { title: "Busy", severity: "warning" },
  damaged: { title: "Damaged", severity: "error" },
  not_sqlite: { title: "Not a SQLite database", severity: "error" },
  unsupported: { title: "Unsupported format", severity: "error" },
  unreadable: { title: "Unreadable", severity: "error" },
  refused: { title: "Refused", severity: "error" },
  reader_stopped: { title: "Reader stopped", severity: "error" },
};

/** How each access mode opened the database. */
/** @type {Record<string, string>} */
const MODES = {
  immutable: "Read as it is, with no lock",
  read_only: "Read through its write-ahead log",
  private_copy: "Read from a private copy",
};

/** @type {Record<string, string>} */
const JOURNALS = {
  rollback: "Rollback journal",
  wal: "Write-ahead log",
};

/** @type {Record<string, [string, string]>} */
const OBJECT_NOUNS = {
  table: ["table", "tables"],
  view: ["view", "views"],
  index: ["index", "indexes"],
  trigger: ["trigger", "triggers"],
};

/**
 * @param {number} count
 * @param {string} kind
 * @param {FormatInteger} formatInteger
 */
function objectCount(count, kind, formatInteger) {
  const nouns = OBJECT_NOUNS[kind] ?? [kind, kind];
  return `${formatInteger(count)} ${count === 1 ? nouns[0] : nouns[1]}`;
}

/**
 * @param {number} value
 * @param {FormatInteger} formatInteger
 */
function bytes(value, formatInteger) {
  return `${formatInteger(value)} ${value === 1 ? "byte" : "bytes"}`;
}

/** @param {number} value */
function hex32(value) {
  return `0x${(value >>> 0).toString(16).toUpperCase().padStart(8, "0")}`;
}

/**
 * @param {InfoSidecar} sidecar
 * @param {FormatInteger} formatInteger
 */
function sidecarText(sidecar, formatInteger) {
  const parts = [bytes(sidecar.size, formatInteger)];
  if (sidecar.name === "-wal" && sidecar.frames !== undefined) {
    parts.push(
      sidecar.frames === 0
        ? "no frames"
        : `${formatInteger(sidecar.frames)} ${sidecar.frames === 1 ? "frame" : "frames"}`,
    );
  }
  if (sidecar.name === "-journal" && sidecar.live !== undefined) {
    parts.push(sidecar.live ? "live: a writer is inside a transaction" : "idle");
  }
  return parts.join(", ");
}

/**
 * The view's model of one answer.
 *
 * @param {InfoPayload} payload
 * @param {{formatInteger: FormatInteger}} format
 * @returns {InfoModel}
 */
export function infoModel(payload, { formatInteger }) {
  /** @type {InfoNotice[]} */
  const notices = [];
  if (payload.error) {
    const state = STATES[payload.error.state] ?? { title: "Unreadable", severity: "error" };
    notices.push({ severity: state.severity, title: state.title, text: payload.error.message });
  }
  const access = payload.access;
  if (access && access.state !== "current") {
    const state = STATES[access.state] ?? STATES.current;
    notices.push({ severity: state.severity, title: state.title, text: access.reason });
  }
  for (const text of access?.notices ?? []) {
    notices.push({ severity: "warning", title: "Created beside the database", text });
  }
  /** @type {InfoSection[]} */
  const sections = [];
  if (access) {
    /** @type {InfoRow[]} */
    const rows = [
      { label: "State", value: STATES[access.state]?.title ?? access.state },
      { label: "Opened", value: MODES[access.mode] ?? access.mode },
      { label: "Why", value: access.reason },
    ];
    if (access.attempts > 1) {
      rows.push({
        label: "Attempts",
        value: formatInteger(access.attempts),
        numeric: true,
      });
    }
    sections.push({ title: "Access", rows });
  }
  const database = payload.database;
  if (database) {
    const objects = Object.entries(database.objects);
    /** @type {InfoRow[]} */
    const rows = [
      {
        label: "Journal",
        value: JOURNALS[payload.journal_mode ?? ""] ?? String(payload.journal_mode),
      },
      { label: "Page size", value: bytes(database.page_size, formatInteger), numeric: true },
      { label: "Pages", value: formatInteger(database.page_count), numeric: true },
      { label: "Free pages", value: formatInteger(database.freelist_count), numeric: true },
      { label: "Encoding", value: database.encoding, literal: true },
      { label: "User version", value: formatInteger(database.user_version), numeric: true },
      {
        label: "Application",
        value:
          database.application_id === 0
            ? "None declared"
            : `${database.application_name ?? "Unknown"} (${hex32(database.application_id)})`,
        muted: database.application_id === 0,
      },
      {
        label: "Schema",
        value: objects.length
          ? objects.map(([kind, count]) => objectCount(count, kind, formatInteger)).join(", ")
          : "Empty",
        muted: objects.length === 0,
      },
    ];
    sections.push({ title: "Database", rows });
  }
  if (payload.sidecars) {
    /** @type {InfoRow[]} */
    const rows = [];
    if (payload.size !== undefined) {
      rows.push({ label: "Main file", value: bytes(payload.size, formatInteger), numeric: true });
    }
    for (const sidecar of payload.sidecars) {
      rows.push({
        label: sidecar.name,
        value: sidecarText(sidecar, formatInteger),
        literal: false,
      });
    }
    if (payload.sidecars.length === 0) {
      rows.push({ label: "Beside it", value: "No journal or log", muted: true });
    }
    if ((payload.links ?? 1) > 1) {
      rows.push({ label: "Names", value: formatInteger(payload.links ?? 1), numeric: true });
    }
    sections.push({ title: "Files", rows });
  }
  const library = payload.library;
  if (library) {
    /** @type {InfoRow[]} */
    const rows = [
      {
        label: "SQLite",
        value: library.meets_minimum
          ? `${library.version}`
          : `${library.version}, older than ${library.minimum}: tables cannot be read`,
        literal: true,
      },
      ...library.versions.map((entry) => ({
        label: entry.version,
        value: `${entry.meaning}${entry.available ? "" : " (not in this library)"}`,
        muted: !entry.available,
      })),
    ];
    sections.push({ title: "Library", rows });
  }
  return { notices, sections };
}
