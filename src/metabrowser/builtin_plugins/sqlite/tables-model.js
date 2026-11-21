// The SQLite overview's and Schema view's models: what each says about one answer.
//
// The overview is a database's Table view at its own address: its tables, views,
// virtual tables, and internal tables, each a link to its address with its estimate,
// from /api/plugin/table/tables. The Schema view lists each object's DDL with its
// indexes and triggers, and every table's foreign keys, from /api/plugin/sqlite/schema,
// for the database or for the one table its address names.
//
// Pure: no DOM and no SDK. The views draw them (tables-view.js), and the browserless
// session (tests/dom/sqlite-tables-session.js) prints them for recorded answers, so what
// the pages say is pinned by a golden.

/**
 * @typedef {object} TableEntry
 * @property {string} id
 * @property {string} label
 * @property {string} group
 * @property {boolean} keyed
 * @property {number | null} estimate
 * @property {string} path
 *
 * @typedef {object} TablesPayload
 * @property {TableEntry[]} [tables]
 *
 * @typedef {object} OverviewRow
 * @property {string} label
 * @property {string} path
 * @property {string} estimate What the estimate column says: "about N rows", or "" for
 *   an object with no cheap estimate.
 * @property {string | null} note "no key" for an object whose rows are named by position.
 *
 * @typedef {object} OverviewGroup
 * @property {string} group
 * @property {string} title
 * @property {OverviewRow[]} rows
 *
 * @typedef {object} OverviewModel
 * @property {OverviewGroup[]} groups
 * @property {string | null} empty What the view says when the database has no tables.
 */

/** The groups in the order the overview draws them, with their headings. */
export const GROUPS = Object.freeze([
  Object.freeze({ group: "tables", title: "Tables" }),
  Object.freeze({ group: "views", title: "Views" }),
  Object.freeze({ group: "virtual", title: "Virtual tables" }),
  Object.freeze({ group: "internal", title: "Internal tables" }),
]);

/**
 * The overview of one tables answer.
 *
 * @param {TablesPayload} payload
 * @param {{formatInteger: (value: number) => string}} format
 * @returns {OverviewModel}
 */
export function overviewModel(payload, format) {
  const entries = payload.tables ?? [];
  /** @type {OverviewGroup[]} */
  const groups = [];
  for (const { group, title } of GROUPS) {
    const rows = entries
      .filter((entry) => entry.group === group)
      .map((entry) => ({
        label: entry.label,
        path: entry.path,
        estimate:
          typeof entry.estimate === "number"
            ? `about ${format.formatInteger(entry.estimate)} ${entry.estimate === 1 ? "row" : "rows"}`
            : "",
        note: entry.keyed || group === "views" || group === "virtual" ? null : "no key",
      }));
    if (rows.length) {
      groups.push({ group, title, rows });
    }
  }
  return { groups, empty: entries.length ? null : "This database has no tables." };
}

/**
 * @typedef {object} SchemaObject
 * @property {string | null} type
 * @property {string | null} name
 * @property {string | null} table
 * @property {string | null} sql
 *
 * @typedef {object} SchemaForeignKey
 * @property {string} table
 * @property {string[]} fields
 * @property {string} references
 * @property {string[]} to
 *
 * @typedef {object} SchemaPayload
 * @property {string | null} [table]
 * @property {SchemaObject[]} [objects]
 * @property {SchemaForeignKey[]} [foreign_keys]
 * @property {{state: string, message: string}} [error]
 *
 * @typedef {object} SchemaEntry
 * @property {string} type
 * @property {string} name
 * @property {string} sql The DDL, or what stands for an object SQLite keeps none for.
 *
 * @typedef {object} SchemaSection
 * @property {string} title The table or view the section is about.
 * @property {SchemaEntry[]} entries Its own DDL first, then its indexes and triggers.
 * @property {string[]} foreignKeys One line per foreign key: `a, b → other (c, d)`.
 *
 * @typedef {object} SchemaModel
 * @property {SchemaSection[]} sections
 * @property {string | null} error
 */

/**
 * The Schema view of one schema answer: a section per table or view, in the order the
 * route lists them.
 *
 * @param {SchemaPayload} payload
 * @returns {SchemaModel}
 */
export function schemaModel(payload) {
  if (payload.error) {
    return { sections: [], error: payload.error.message };
  }
  /** @type {Map<string, SchemaSection>} */
  const sections = new Map();
  for (const object of payload.objects ?? []) {
    const table = object.table ?? object.name ?? "";
    let section = sections.get(table);
    if (!section) {
      section = { title: table, entries: [], foreignKeys: [] };
      sections.set(table, section);
    }
    section.entries.push({
      type: object.type ?? "",
      name: object.name ?? "",
      sql: object.sql ?? `(${object.type ?? "object"} created by SQLite, with no DDL)`,
    });
  }
  for (const key of payload.foreign_keys ?? []) {
    const section = sections.get(key.table);
    if (section) {
      section.foreignKeys.push(
        `${key.fields.join(", ")} → ${key.references} (${key.to.join(", ")})`,
      );
    }
  }
  return { sections: [...sections.values()], error: null };
}
