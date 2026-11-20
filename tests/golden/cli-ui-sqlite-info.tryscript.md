---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the SQLite Info view

The sqlite plugin’s Info view says what a reader process saw of a database: how it
opened it and why, the database as its connection reads it, the files beside it, and
the SQLite library against the reader’s minimum.
What the route answers is pinned by `cli-api-sqlite.tryscript.md`; this session pins
what the page draws from each answer.
It loads the plugin’s production modules, `info-model.js` and `info-view.js`, and mounts
the view on the answers in `tests/fixtures/sqlite-info-responses.json`, which
`tests/test_sqlite_info_session.py` records from the route over a database in each
state: a rollback-journal database, an idle write-ahead-log one with no extension, a
crashed owner’s log read through its index, a log with no index read through a private
copy, a file with a second name, a writer killed inside a transaction, and a file that
is not a database.

A state other than Current is a notice: a warning for one a later read may clear, an
error for one it will not. The library recorded is one that meets the minimum; the
session also draws an older one, a request that fails, and a view disposed before its
answer arrives, which draws nothing.

```console
$ node tests/dom/sqlite-info-session.js
{
  "answers": {
    "app.db": {
      "notices": [],
      "sections": {
        "Access": [
          "State: Current",
          "Opened: Read as it is, with no lock",
          "Why: a rollback-journal database is read without a lock, validated against a commit"
        ],
        "Database": [
          "Journal: Rollback journal",
          "Page size: 4,096 bytes  {sqlite-info-number}",
          "Pages: 3  {sqlite-info-number}",
          "Free pages: 0  {sqlite-info-number}",
          "Encoding: UTF-8  {data-literal}",
          "User version: 7  {sqlite-info-number}",
          "Application: fsqlite snapshot (0x4653514C)",
          "Schema: 1 index, 1 table, 1 trigger, 1 view"
        ],
        "Files": [
          "Main file: 12,288 bytes  {sqlite-info-number}",
          "Beside it: No journal or log  {sqlite-info-muted}"
        ],
        "Library": [
          "SQLite: L  {data-literal}",
          "3.7.0: write-ahead-log databases",
          "3.8.2: WITHOUT ROWID tables",
          "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
          "3.31.0: PRAGMA trusted_schema and generated columns",
          "3.37.0: STRICT tables",
          "3.43.0: octet_length(), the reader's minimum for reading tables",
          "3.45.0: JSONB values"
        ]
      }
    },
    "History": {
      "notices": [],
      "sections": {
        "Access": [
          "State: Current",
          "Opened: Read as it is, with no lock",
          "Why: the write-ahead log holds no frames, so the main file is read without a lock, validated against a new frame or checkpoint"
        ],
        "Database": [
          "Journal: Write-ahead log",
          "Page size: 4,096 bytes  {sqlite-info-number}",
          "Pages: 2  {sqlite-info-number}",
          "Free pages: 0  {sqlite-info-number}",
          "Encoding: UTF-8  {data-literal}",
          "User version: 0  {sqlite-info-number}",
          "Application: None declared  {sqlite-info-muted}",
          "Schema: 1 table"
        ],
        "Files": [
          "Main file: 8,192 bytes  {sqlite-info-number}",
          "Beside it: No journal or log  {sqlite-info-muted}"
        ],
        "Library": [
          "SQLite: L  {data-literal}",
          "3.7.0: write-ahead-log databases",
          "3.8.2: WITHOUT ROWID tables",
          "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
          "3.31.0: PRAGMA trusted_schema and generated columns",
          "3.37.0: STRICT tables",
          "3.43.0: octet_length(), the reader's minimum for reading tables",
          "3.45.0: JSONB values"
        ]
      }
    },
    "live.db": {
      "notices": [],
      "sections": {
        "Access": [
          "State: Current",
          "Opened: Read through its write-ahead log",
          "Why: the write-ahead log holds frames and its index is present, so it is read through them as every reader does"
        ],
        "Database": [
          "Journal: Write-ahead log",
          "Page size: 4,096 bytes  {sqlite-info-number}",
          "Pages: 2  {sqlite-info-number}",
          "Free pages: 0  {sqlite-info-number}",
          "Encoding: UTF-8  {data-literal}",
          "User version: 0  {sqlite-info-number}",
          "Application: None declared  {sqlite-info-muted}",
          "Schema: 1 table"
        ],
        "Files": [
          "Main file: 8,192 bytes  {sqlite-info-number}",
          "-wal: 20,632 bytes, 5 frames",
          "-shm: 32,768 bytes"
        ],
        "Library": [
          "SQLite: L  {data-literal}",
          "3.7.0: write-ahead-log databases",
          "3.8.2: WITHOUT ROWID tables",
          "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
          "3.31.0: PRAGMA trusted_schema and generated columns",
          "3.37.0: STRICT tables",
          "3.43.0: octet_length(), the reader's minimum for reading tables",
          "3.45.0: JSONB values"
        ]
      }
    },
    "noshm.db": {
      "notices": [],
      "sections": {
        "Access": [
          "State: Current",
          "Opened: Read from a private copy",
          "Why: the write-ahead log holds frames and has no index beside it, so the database and its log are read through a private copy"
        ],
        "Database": [
          "Journal: Write-ahead log",
          "Page size: 4,096 bytes  {sqlite-info-number}",
          "Pages: 2  {sqlite-info-number}",
          "Free pages: 0  {sqlite-info-number}",
          "Encoding: UTF-8  {data-literal}",
          "User version: 0  {sqlite-info-number}",
          "Application: None declared  {sqlite-info-muted}",
          "Schema: 1 table"
        ],
        "Files": [
          "Main file: 8,192 bytes  {sqlite-info-number}",
          "-wal: 20,632 bytes, 5 frames"
        ],
        "Library": [
          "SQLite: L  {data-literal}",
          "3.7.0: write-ahead-log databases",
          "3.8.2: WITHOUT ROWID tables",
          "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
          "3.31.0: PRAGMA trusted_schema and generated columns",
          "3.37.0: STRICT tables",
          "3.43.0: octet_length(), the reader's minimum for reading tables",
          "3.45.0: JSONB values"
        ]
      }
    },
    "linked.db": {
      "notices": [
        "[warning, status] Another name: this file has 2 names; a journal or log kept beside another name is not shown"
      ],
      "sections": {
        "Access": [
          "State: Another name",
          "Opened: Read from a private copy",
          "Why: this file has 2 names; a journal or log kept beside another name is not shown"
        ],
        "Database": [
          "Journal: Write-ahead log",
          "Page size: 4,096 bytes  {sqlite-info-number}",
          "Pages: 2  {sqlite-info-number}",
          "Free pages: 0  {sqlite-info-number}",
          "Encoding: UTF-8  {data-literal}",
          "User version: 0  {sqlite-info-number}",
          "Application: None declared  {sqlite-info-muted}",
          "Schema: 1 table"
        ],
        "Files": [
          "Main file: 8,192 bytes  {sqlite-info-number}",
          "Beside it: No journal or log  {sqlite-info-muted}",
          "Names: 2  {sqlite-info-number}"
        ],
        "Library": [
          "SQLite: L  {data-literal}",
          "3.7.0: write-ahead-log databases",
          "3.8.2: WITHOUT ROWID tables",
          "3.26.0: SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
          "3.31.0: PRAGMA trusted_schema and generated columns",
          "3.37.0: STRICT tables",
          "3.43.0: octet_length(), the reader's minimum for reading tables",
          "3.45.0: JSONB values"
        ]
      }
    },
    "busy.db": {
      "notices": [
        "[warning, status] Writer busy: The application that owns this database is writing to it."
      ],
      "sections": {}
    },
    "fake.db": {
      "notices": [
        "[error, alert] Not a SQLite database: This file is not a SQLite database."
      ],
      "sections": {}
    }
  },
  "an older library": [
    {
      "label": "SQLite",
      "value": "3.40.1, older than 3.43.0: tables cannot be read",
      "literal": true
    },
    {
      "label": "3.7.0",
      "value": "write-ahead-log databases",
      "muted": false
    },
    {
      "label": "3.8.2",
      "value": "WITHOUT ROWID tables",
      "muted": false
    },
    {
      "label": "3.26.0",
      "value": "SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
      "muted": false
    },
    {
      "label": "3.31.0",
      "value": "PRAGMA trusted_schema and generated columns",
      "muted": false
    },
    {
      "label": "3.37.0",
      "value": "STRICT tables",
      "muted": false
    },
    {
      "label": "3.43.0",
      "value": "octet_length(), the reader's minimum for reading tables (not in this library)",
      "muted": true
    },
    {
      "label": "3.45.0",
      "value": "JSONB values (not in this library)",
      "muted": true
    }
  ],
  "a request that fails": {
    "notices": [
      "[error, alert] Unreadable: Not found"
    ],
    "sections": {}
  },
  "a view disposed before its answer": {
    "notices": [],
    "sections": {},
    "loading": "Reading this database…"
  }
}
? 0
```
