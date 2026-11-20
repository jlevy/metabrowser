---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the SQLite overview, Schema view, and table cells

A SQLite database is a navigation container whose children are its tables, each at
`<database>/<segment>`. Its Table view at the database’s own address is an overview of
its tables, views, virtual tables, and internal tables, each a link to its address with
the catalog’s estimate of its rows; at a table’s address it is the table plugin’s view
of that table, loaded on demand.
Its Schema view lists each object’s DDL with its indexes and triggers, and each table’s
foreign keys, for the database or for the table its address names.
The routes each reads are pinned by `metab --api` in
`cli-api-sqlite-tables.tryscript.md`; this session pins what the pages do with the
answers.

It loads the sqlite plugin’s production modules, `tables-model.js` and `tables-view.js`,
and the table plugin’s `table-model.js`, and draws each view from the answers recorded
in `tests/fixtures/sqlite-tables-responses.json` by
`tests/test_sqlite_tables_session.py` over the databases built from
`tests/fixtures/sqlite-tables/`. A plain click on an overview link opens the table in
place, and a Command-click is left to the browser.
Every cell of four recorded pages is presented as the table view draws it: a reference
to a row that is not there is its value marked missing, a value too long for a page is
cut with its size in characters or, where only the stored bytes were read, in bytes, a
blob is its hex with its size, and a value stored as another type than its column’s says
so.
A request that fails is said in place of the overview, and a view disposed before its
answer draws nothing.

## Test: the session

```console
$ node tests/dom/sqlite-tables-session.js
{
  "overview of app.db": {
    "Tables": [
      "blobs → /view/app.db/blobs",
      "counters → /view/app.db/counters  about 2 rows",
      "g1-like → /view/app.db/~67312d6c696b65",
      "grants → /view/app.db/grants  about 3 rows",
      "huge → /view/app.db/huge  about 2 rows",
      "order items → /view/app.db/~6f72646572206974656d73  about 1 row",
      "orders → /view/app.db/orders  about 5 rows",
      "prices → /view/app.db/prices  about 2 rows",
      "shadows → /view/app.db/shadows  (no key)",
      "tags → /view/app.db/tags",
      "users → /view/app.db/users  about 6 rows",
      "~tilde → /view/app.db/~7e74696c6465"
    ],
    "Views": [
      "shouting → /view/app.db/shouting"
    ],
    "Virtual tables": [
      "notes → /view/app.db/notes"
    ],
    "Internal tables": [
      "notes_config → /view/app.db/notes_config  (no key)",
      "notes_content → /view/app.db/notes_content  (no key)",
      "notes_data → /view/app.db/notes_data  (no key)",
      "notes_docsize → /view/app.db/notes_docsize  (no key)",
      "notes_idx → /view/app.db/notes_idx  (no key)",
      "sqlite_sequence → /view/app.db/sqlite_sequence  about 1 row"
    ]
  },
  "an overview link, clicked and Command-clicked": {
    "opened": [
      "app.db/blobs"
    ],
    "prevented": 1
  },
  "overview of snapshot.db": {
    "Tables": [
      "items → /view/snapshot.db/items  about 1 row"
    ],
    "Internal tables": [
      "applied_tx → /view/snapshot.db/applied_tx",
      "fsqlite_meta → /view/snapshot.db/fsqlite_meta"
    ]
  },
  "schema of app.db": {
    "blobs": [
      "CREATE TABLE blobs (k BLOB PRIMARY KEY, v TEXT) WITHOUT ROWID"
    ],
    "counters": [
      "CREATE TABLE counters (id INTEGER PRIMARY KEY AUTOINCREMENT, n INTEGER)"
    ],
    "g1-like": [
      "CREATE TABLE \"g1-like\" (id INTEGER PRIMARY KEY)"
    ],
    "grants": [
      "CREATE TABLE grants (\n  id INTEGER PRIMARY KEY,\n  owner INTEGER,\n  tag TEXT,\n  FOREIGN KEY (owner, tag) REFERENCES tags(owner, tag)\n)",
      "FK owner, tag → tags (owner, tag)"
    ],
    "huge": [
      "CREATE TABLE huge (id INTEGER PRIMARY KEY, body TEXT)"
    ],
    "notes": [
      "CREATE VIRTUAL TABLE notes USING fts5(body)"
    ],
    "notes_config": [
      "CREATE TABLE 'notes_config'(k PRIMARY KEY, v) WITHOUT ROWID"
    ],
    "notes_content": [
      "CREATE TABLE 'notes_content'(id INTEGER PRIMARY KEY, c0)"
    ],
    "notes_data": [
      "CREATE TABLE 'notes_data'(id INTEGER PRIMARY KEY, block BLOB)"
    ],
    "notes_docsize": [
      "CREATE TABLE 'notes_docsize'(id INTEGER PRIMARY KEY, sz BLOB)"
    ],
    "notes_idx": [
      "CREATE TABLE 'notes_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID"
    ],
    "order items": [
      "CREATE TABLE \"order items\" (id INTEGER PRIMARY KEY, what TEXT)"
    ],
    "orders": [
      "CREATE TABLE orders (\n  user_id INTEGER REFERENCES users(id),\n  total REAL,\n  note TEXT\n)",
      "FK user_id → users (id)"
    ],
    "prices": [
      "CREATE TABLE prices (\n  item TEXT PRIMARY KEY,\n  cents INTEGER NOT NULL,\n  dollars REAL GENERATED ALWAYS AS (cents / 100.0) VIRTUAL,\n  label TEXT GENERATED ALWAYS AS (upper(item)) STORED\n) STRICT",
      "(index created by SQLite, with no DDL)"
    ],
    "shadows": [
      "CREATE TABLE shadows (rowid TEXT, _rowid_ TEXT, oid TEXT)"
    ],
    "shouting": [
      "CREATE VIEW shouting AS SELECT upper(name) AS name, length(name) AS letters FROM users"
    ],
    "sqlite_sequence": [
      "CREATE TABLE sqlite_sequence(name,seq)"
    ],
    "tags": [
      "CREATE TABLE tags (\n  owner INTEGER NOT NULL,\n  tag TEXT NOT NULL COLLATE NOCASE,\n  PRIMARY KEY (owner, tag)\n) WITHOUT ROWID"
    ],
    "users": [
      "CREATE TABLE users (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  email TEXT,\n  age INTEGER,\n  active BOOLEAN,\n  joined DATE,\n  prefs JSON,\n  avatar BLOB,\n  bio TEXT\n)",
      "CREATE INDEX users_email ON users(email)"
    ],
    "~tilde": [
      "CREATE TABLE \"~tilde\" (id INTEGER PRIMARY KEY)"
    ]
  },
  "schema of app.db/grants": {
    "grants": [
      "CREATE TABLE grants (\n  id INTEGER PRIMARY KEY,\n  owner INTEGER,\n  tag TEXT,\n  FOREIGN KEY (owner, tag) REFERENCES tags(owner, tag)\n)",
      "FK owner, tag → tags (owner, tag)"
    ]
  },
  "schema of fake.db": {
    "alert": "[alert] This file is not a SQLite database."
  },
  "the Table view at a table's address": {
    "loaded": [
      "table"
    ],
    "mounted": "app.db/users",
    "drawn": [
      "table-view"
    ]
  },
  "cells of app.db/users": [
    [
      "id: number \"1\"  {literal}",
      "name: text \"Ada\"",
      "email: text \"ada@example.com\"",
      "age: number \"36\"",
      "active: boolean \"true\"",
      "joined: text \"2020-01-02\"  {literal}",
      "prefs: json \"{\\\"theme\\\":\\\"dark\\\"}\"  {literal}",
      "avatar: blob \"00ff10\"  {cut 3, literal}",
      "bio: null \"null\"  {literal}"
    ],
    [
      "id: number \"2\"  {literal}",
      "name: text \"Bob\"",
      "email: null \"null\"  {literal}",
      "age: text \"unknown\"  {stored text}",
      "active: boolean \"false\"",
      "joined: text \"2021-03-04\"  {literal}",
      "prefs: text \"not json\"  {literal}",
      "avatar: null \"null\"  {literal}",
      "bio: empty \"\""
    ],
    [
      "id: number \"3\"  {literal}",
      "name: text \"Cy\"",
      "email: text \"cy@example.com\"",
      "age: number \"9007199254740993\"",
      "active: boolean \"true\"",
      "joined: null \"null\"  {literal}",
      "prefs: json \"[1,2]\"  {literal}",
      "avatar: null \"null\"  {literal}",
      "bio: text \"000000000000000000000000…\"  {size 5200}"
    ],
    [
      "id: number \"4\"  {literal}",
      "name: text \"Dee\"",
      "email: null \"null\"  {literal}",
      "age: number \"-9223372036854775808\"",
      "active: number \"2\"  {stored integer}",
      "joined: text \"2019-12-31\"  {literal}",
      "prefs: null \"null\"  {literal}",
      "avatar: blob \"000000000000000000000000…\"  {cut 300, literal}",
      "bio: null \"null\"  {literal}"
    ],
    [
      "id: number \"5\"  {literal}",
      "name: text \"Eve\"",
      "email: text \"EVE@example.com\"",
      "age: number \"41\"",
      "active: boolean \"true\"",
      "joined: number \"20230101\"  {literal}",
      "prefs: null \"null\"  {literal}",
      "avatar: null \"null\"  {literal}",
      "bio: text \"�A\"  {invalid}"
    ],
    [
      "id: number \"6\"  {literal}",
      "name: text \"Fay\"",
      "email: text \"7\"",
      "age: number \"29\"",
      "active: boolean \"false\"",
      "joined: text \"2018-05-06\"  {literal}",
      "prefs: null \"null\"  {literal}",
      "avatar: null \"null\"  {literal}",
      "bio: null \"null\"  {literal}"
    ]
  ],
  "cells of app.db/orders": [
    [
      "user_id: ref \"1\"  {ref users}",
      "total: number \"9.5\"",
      "note: text \"first\""
    ],
    [
      "user_id: ref \"1\"  {ref users}",
      "total: number \"Infinity\"",
      "note: null \"null\"  {literal}"
    ],
    [
      "user_id: ref \"2\"  {ref users}",
      "total: number \"−Infinity\"",
      "note: text \"second\""
    ],
    [
      "user_id: text \"99\"  {missing}",
      "total: number \"0.5\"",
      "note: text \"dangling\""
    ],
    [
      "user_id: null \"null\"  {literal}",
      "total: null \"null\"  {literal}",
      "note: text \"no user\""
    ]
  ],
  "cells of app.db/grants": [
    [
      "id: number \"1\"  {literal}",
      "owner: ref \"1\"  {ref tags}",
      "tag: ref \"ADMIN\"  {ref tags}"
    ],
    [
      "id: number \"2\"  {literal}",
      "owner: ref \"3\"  {ref tags}",
      "tag: ref \"beta\"  {ref tags}"
    ],
    [
      "id: number \"3\"  {literal}",
      "owner: text \"2\"  {missing}",
      "tag: text \"gamma\"  {missing}"
    ]
  ],
  "cells of app.db/huge": [
    [
      "id: number \"1\"  {literal}",
      "body: text \"small\""
    ],
    [
      "id: number \"2\"  {literal}",
      "body: text \"000000000000000000000000…\"  {size 1200000}"
    ]
  ],
  "a request that fails": {
    "said": "Nothing recorded for tables"
  },
  "a view disposed before its answer": {}
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
