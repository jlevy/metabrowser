---
cwd: ../..
sandbox: false
---
# Golden Test: The fsqlite Store’s Info View

The fsqlite plugin shows a store as a reader sees it: the store’s own section, from
`builtin_plugins/fsqlite/store-model.js`, then the snapshot `current` names as the
SQLite plugin’s Info view shows a database, drawn by that plugin’s `drawInfo`, which the
store’s view reaches through the SQLite plugin’s exports.

This browserless session mounts the production view (`store-view.js`) over the answers
`/api/plugin/fsqlite/info` gave for six stores, recorded in
`tests/fixtures/fsqlite-info-responses.json` by `tests/test_fsqlite_info_session.py`,
which fails when the route answers differently.
A generation is recorded as `G` and the SQLite library’s version as `L`. The transcript
pins these behaviors:

- A store’s section comes first: its format, its identity, the version `current` names,
  that snapshot’s path, and its pending transaction envelopes; the snapshot’s Access,
  Database, Files, and Library sections follow.
- Pending envelopes read as committed ones waiting for the next reconcile and
  uncommitted ones in flight or torn, “None” when there are none, and “at least” when
  the count stopped at its bound.
- A store that cannot be shown says its state in an alert: a pointer that is not ASCII
  digits is corrupt, a format version the reader does not know is unsupported, and a
  snapshot without fsqlite’s `application_id` is corrupt.
- A snapshot the reader cannot read keeps the store’s section and says the reader’s
  state.
- A pointer read again after garbage collection says so.
- A view disposed before its answer draws nothing and aborts its request; a refused
  request reads as an unreadable store in the route’s words; and a SQLite plugin that
  failed to load is said, never a blank page.

```console
$ node tests/dom/fsqlite-info-session.js
{
  "stores": {
    "notes/fsqlite.json": [
      "## Store",
      "Format: fsqlite f1.0  (literal)",
      "Store: 550e8400-e29b-41d4-a716-446655440000  (literal)",
      "Version: 2  (number)",
      "Snapshot: snapshots/000000000002.fsqlite.sqlite  (literal)",
      "Pending: 2 committed envelopes waiting for the next reconcile; 1 uncommitted envelope, in flight or torn",
      "## Access",
      "State: Current",
      "Opened: Read as it is, with no lock",
      "Why: content that cannot change is read as it is",
      "## Database",
      "Journal: Rollback journal",
      "Page size: 4,096 bytes  (number)",
      "Pages: 6  (number)",
      "Free pages: 0  (number)",
      "Encoding: UTF-8  (literal)",
      "User version: 3  (number)",
      "Application: fsqlite snapshot (0x4653514C)",
      "Schema: 2 indexes, 3 tables",
      "## Files",
      "Main file: 24,576 bytes  (number)",
      "Beside it: No journal or log  (muted)",
      "## Library",
      "SQLite: L  (literal)",
      "3.7.0: write-ahead-log databases",
      "3.8.2: WITHOUT ROWID tables",
      "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
      "3.31.0: PRAGMA trusted_schema and generated columns",
      "3.37.0: STRICT tables",
      "3.43.0: octet_length(), the reader's minimum for reading tables",
      "3.45.0: JSONB values"
    ],
    "empty/fsqlite.json": [
      "## Store",
      "Format: fsqlite f1.0  (literal)",
      "Store: 550e8400-e29b-41d4-a716-446655440000  (literal)",
      "Version: 0  (number)",
      "Snapshot: snapshots/000000000000.fsqlite.sqlite  (literal)",
      "Pending: None  (muted)",
      "## Access",
      "State: Current",
      "Opened: Read as it is, with no lock",
      "Why: content that cannot change is read as it is",
      "## Database",
      "Journal: Rollback journal",
      "Page size: 4,096 bytes  (number)",
      "Pages: 6  (number)",
      "Free pages: 0  (number)",
      "Encoding: UTF-8  (literal)",
      "User version: 3  (number)",
      "Application: fsqlite snapshot (0x4653514C)",
      "Schema: 2 indexes, 3 tables",
      "## Files",
      "Main file: 24,576 bytes  (number)",
      "Beside it: No journal or log  (muted)",
      "## Library",
      "SQLite: L  (literal)",
      "3.7.0: write-ahead-log databases",
      "3.8.2: WITHOUT ROWID tables",
      "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
      "3.31.0: PRAGMA trusted_schema and generated columns",
      "3.37.0: STRICT tables",
      "3.43.0: octet_length(), the reader's minimum for reading tables",
      "3.45.0: JSONB values"
    ],
    "torn/fsqlite.json": [
      "[error alert] Corrupt store: The current pointer does not name a version: “\\xef\\xbb\\xbf7”.",
      "## Store",
      "Format: fsqlite f1.0  (literal)",
      "Store: 550e8400-e29b-41d4-a716-446655440000  (literal)",
      "Pending: None  (muted)"
    ],
    "newer/fsqlite.json": [
      "[error alert] Unsupported store: This store's format f2.0 is newer than this reader knows."
    ],
    "foreign/fsqlite.json": [
      "[error alert] Corrupt store: The snapshot's application_id is 0x00000000, not fsqlite's 0x4653514c (“FSQL”).",
      "## Store",
      "Format: fsqlite f1.0  (literal)",
      "Store: 550e8400-e29b-41d4-a716-446655440000  (literal)",
      "Pending: None  (muted)"
    ],
    "garbled/fsqlite.json": [
      "[error alert] Not a SQLite database: This file is not a SQLite database.",
      "## Store",
      "Format: fsqlite f1.0  (literal)",
      "Store: 550e8400-e29b-41d4-a716-446655440000  (literal)",
      "Version: 1  (number)",
      "Snapshot: snapshots/000000000001.fsqlite.sqlite  (literal)",
      "Pending: None  (muted)"
    ]
  },
  "lifecycle": {
    "a pointer read again": "Pointer: Read again: the snapshot it first named was collected",
    "pending": [
      "None",
      "1 committed envelope waiting for the next reconcile",
      "2 uncommitted envelopes, in flight or torn",
      "at least 1,200 committed envelopes waiting for the next reconcile; at least 3 uncommitted envelopes, in flight or torn",
      "Not counted: too many entries"
    ],
    "disposed before its answer": [
      "(Reading this store…)"
    ],
    "a refused request": [
      "[error alert] Unreadable store: This is not an fsqlite store's marker."
    ],
    "the SQLite plugin failed to load": [
      "(Could not load the SQLite plugin this view draws with.)"
    ]
  }
}
? 0
```
