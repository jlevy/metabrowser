---
cwd: ../..
sandbox: false
---
# Golden Test: The fsqlite Store’s Table and Schema Views

A store’s tables are the tables of the snapshot its `current` names, each at
`<marker>/<segment>` as a database’s are at `<database>/<segment>`. The store’s Table
and Schema views, `builtin_plugins/fsqlite/store-tables.js`, are the SQLite plugin’s,
which they reach through that plugin’s exports: Table is the store’s overview at the
marker’s address and the table plugin’s view at a table’s, and Schema reads the store’s
own `fsqlite/schema` route, which answers as `sqlite/schema` does.

This browserless session mounts the production views over the answers the routes gave,
recorded in `tests/fixtures/fsqlite-tables-responses.json` by
`tests/test_fsqlite_tables_session.py`, which fails when a route answers differently.
The table plugin is a stand-in. The transcript pins these behaviors:

- The overview groups the format’s `applied_tx` and `fsqlite_meta` as internal tables,
  each a link to its address under the marker.
- At a table’s address the Table view loads the table plugin and draws its view.
- The Schema view shows the snapshot’s DDL, or one table’s at its address.
- A store the routes refuse says why, in the routes’ words.
- A view disposed before the SQLite plugin loads mounts nothing and asks for nothing; one
  disposed once drawn disposes the SQLite view, aborting its request; and a SQLite plugin
  that failed to load is said, never a blank page.

```console
$ node tests/dom/fsqlite-tables-session.js
{
  "Table view of notes/fsqlite.json": {
    "Tables": [
      "notes → /view/notes/fsqlite.json/notes  about 2 rows"
    ],
    "Internal tables": [
      "applied_tx → /view/notes/fsqlite.json/applied_tx  ",
      "fsqlite_meta → /view/notes/fsqlite.json/fsqlite_meta  "
    ]
  },
  "Table view of torn/fsqlite.json": {
    "said": "The current pointer does not name a version: “one”."
  },
  "Table view of notes/fsqlite.json/notes": {
    "loaded": [
      "sqlite",
      "table"
    ],
    "drawn": [
      "table-view"
    ]
  },
  "Schema view of notes/fsqlite.json": {
    "applied_tx": [
      "CREATE TABLE applied_tx (tx_id TEXT PRIMARY KEY NOT NULL, applied_at TEXT NOT NULL)",
      "(index created by SQLite, with no DDL)"
    ],
    "fsqlite_meta": [
      "CREATE TABLE fsqlite_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)",
      "(index created by SQLite, with no DDL)"
    ],
    "notes": [
      "CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
    ]
  },
  "Schema view of notes/fsqlite.json/notes": {
    "notes": [
      "CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
    ]
  },
  "Schema view of torn/fsqlite.json": {
    "said": "[alert] The current pointer does not name a version: “one”."
  },
  "disposed before the SQLite plugin loads": {
    "asked": [],
    "drawn": 0
  },
  "disposed once drawn": {
    "aborted": [
      "schema"
    ]
  },
  "the SQLite plugin failed to load": {
    "said": "Could not load the SQLite plugin this view draws with."
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
