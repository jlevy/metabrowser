---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  sql() {
  PYTHONPATH="$TRYSCRIPT_TEST_DIR/../.."
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python -m tests.sqlite_text_fixture "$1";
  } &&
  marker() {
  printf '{"format": "fsqlite", "format_version": "%s", "required_features": [], "store_id": "550e8400-e29b-41d4-a716-446655440000"}\n' "$2" > "$1/fsqlite.json";
  } &&
  snapshot() {
  mkdir -p "$1/snapshots" &&
  printf "PRAGMA application_id = $3;
  PRAGMA user_version = 3;
  CREATE TABLE applied_tx (tx_id TEXT PRIMARY KEY NOT NULL, applied_at TEXT NOT NULL);
  CREATE TABLE fsqlite_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
  INSERT INTO fsqlite_meta VALUES ('format_version', 'f1.0'), ('store_id', '550e8400-e29b-41d4-a716-446655440000'), ('schema_hash', '0123456789abcdef'), ('tool_version', 'fixture');
  CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL);
  INSERT INTO notes VALUES (1, 'first');
  INSERT INTO notes SELECT 2, 'second' WHERE $2 >= 2;
  INSERT INTO applied_tx SELECT '000000000001-000000000001-fixture-0123456789', '2026-11-20T00:00:00Z' WHERE $2 >= 2;
  " | sql "$1/snapshots/$(printf '%012d' "$2").fsqlite.sqlite";
  } &&
  mkdir -p storeroot/notes/tx/pending/000000000002-000000000001-fixture-aaaaaaaaaa.txn storeroot/notes/tx/pending/000000000003-000000000002-fixture-bbbbbbbbbb.txn &&
  marker storeroot/notes f1.0 && snapshot storeroot/notes 1 1179865420 && snapshot storeroot/notes 2 1179865420 &&
  printf '2\n' > storeroot/notes/current &&
  touch storeroot/notes/tx/pending/000000000002-000000000001-fixture-aaaaaaaaaa.txn/COMMITTED &&
  touch storeroot/notes/tx/pending/.work-fixture-cccccccccc.sqlite &&
  mkdir -p storeroot/torn && marker storeroot/torn f1.0 && snapshot storeroot/torn 1 1179865420 && printf 'one' > storeroot/torn/current &&
  mkdir -p storeroot/collected && marker storeroot/collected f1.0 && snapshot storeroot/collected 1 1179865420 && printf '5' > storeroot/collected/current &&
  mkdir -p storeroot/newer && marker storeroot/newer f2.0 && printf '0' > storeroot/newer/current &&
  mkdir -p storeroot/foreign && marker storeroot/foreign f1.0 && snapshot storeroot/foreign 1 0 && printf '1' > storeroot/foreign/current &&
  mkdir -p storeroot/other && printf '{"format": "parquet"}\n' > storeroot/other/fsqlite.json &&
  find storeroot -exec touch -h -t 202311142213.20 {} + &&
  find storeroot | LC_ALL=C sort > listing-before.txt &&
  find storeroot -type f -exec cksum {} + | LC_ALL=C sort > sums-before.txt
---
# Golden tests: fsqlite stores

An fsqlite store is a directory holding `fsqlite.json`, whose `current` file names the
published version, an immutable snapshot `snapshots/<version>.fsqlite.sqlite`. The
marker is the `sqlite-store` kind, recognized by its name and its `format`, and the
store is read as a guest: the marker, the pointer, and a listing of the pending
envelopes in the server, and the snapshot in a reader process with `immutable=1`. Every
store here is built in the `before:` script from SQL text and a `current` file.

The generation is the version `current` names, then a hash of the identities of
`fsqlite.json` and `current`, which differ from one checkout to the next, so the
transcripts elide the hash.
The SQLite library’s version is the machine’s, so the transcripts elide it.

## Test: the marker is the store’s kind, and a file merely named so is not

```console
$ metab storeroot --show notes/fsqlite.json
show: notes/fsqlite.json
route: /view/notes/fsqlite.json
kind: sqlite-store
views: table (default, key V), schema (key S), info (key I)
model: text envelope; size=125 content_bytes=125 content_truncated=False
? 0
```

```console
$ metab storeroot --show other/fsqlite.json > other.txt
? 0
```

```console
$ grep '^kind:' other.txt
kind: structured
? 0
```

A snapshot opened by itself is a SQLite database, named by its `application_id`.

```console
$ metab storeroot --show notes/snapshots/000000000002.fsqlite.sqlite > snapshot.txt
? 0
```

```console
$ grep '^kind:' snapshot.txt
kind: sqlite
? 0
```

## Test: Info reads the snapshot `current` names and counts the pending envelopes

`current` names version 2, so version 1’s snapshot, still on disk, is not read.
One envelope is committed and waits for the next reconcile; the other has no `COMMITTED`
marker, a capture in flight or torn; the `.work-` working copy is not an envelope.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=notes/fsqlite.json'
api: /api/plugin/fsqlite/info?path=notes/fsqlite.json
status: 200
{
  "type": "fsqlite_info",
  "path": "notes/fsqlite.json",
  "generation": "2-[..]",
  "store": {
    "format_version": "f1.0",
    "store_id": "550e8400-e29b-41d4-a716-446655440000",
    "required_features": [],
    "pending": {
      "committed": 1,
      "uncommitted": 1,
      "complete": true
    },
    "version": 2,
    "snapshot": "000000000002.fsqlite.sqlite",
    "attempts": 1
  },
  "snapshot": {
    "access": {
      "mode": "immutable",
      "state": "current",
      "reason": "content that cannot change is read as it is",
      "attempts": 1,
      "notices": []
    },
    "journal_mode": "rollback",
    "links": 1,
    "size": 24576,
    "sidecars": [],
    "database": {
      "page_size": 4096,
      "page_count": 6,
      "encoding": "UTF-8",
      "user_version": 3,
      "application_id": 1179865420,
      "application_name": "fsqlite snapshot",
      "freelist_count": 0,
      "objects": {
        "index": 2,
        "table": 3
      }
    },
    "library": {
      "version": "[..]",
      "minimum": "3.43.0",
      "meets_minimum": true,
      "versions": [
        {
          "version": "3.7.0",
          "meaning": "write-ahead-log databases",
          "available": true
        },
        {
          "version": "3.8.2",
          "meaning": "WITHOUT ROWID tables",
          "available": true
        },
        {
          "version": "3.26.0",
          "meaning": "SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
          "available": true
        },
        {
          "version": "3.31.0",
          "meaning": "PRAGMA trusted_schema and generated columns",
          "available": true
        },
        {
          "version": "3.37.0",
          "meaning": "STRICT tables",
          "available": true
        },
        {
          "version": "3.43.0",
          "meaning": "octet_length(), the reader's minimum for reading tables",
          "available": true
        },
        {
          "version": "3.45.0",
          "meaning": "JSONB values",
          "available": true
        }
      ]
    }
  }
}
? 0
```

## Test: the store’s tables are its snapshot’s

The store is a container whose children are the tables of the snapshot `current` names,
each at `<marker>/<segment>` as a database’s are, with the snapshot it read.
`applied_tx` and `fsqlite_meta`, the format’s own, are muted as internal.

```console
$ metab storeroot --api '/api/plugin/fsqlite/children?path=notes/fsqlite.json'
api: /api/plugin/fsqlite/children?path=notes/fsqlite.json
status: 200
{
  "children": [
    {
      "name": "applied_tx",
      "path": "notes/fsqlite.json/applied_tx",
      "muted": true
    },
    {
      "name": "fsqlite_meta",
      "path": "notes/fsqlite.json/fsqlite_meta",
      "muted": true
    },
    {
      "name": "notes",
      "path": "notes/fsqlite.json/notes"
    }
  ],
  "version": 2,
  "snapshot": "000000000002.fsqlite.sqlite"
}
? 0
```

The table routes read the store through the SQLite source over that snapshot, under the
store’s generation: its tables by group, then one table’s schema and rows.

```console
$ metab storeroot --api '/api/plugin/table/tables?path=notes/fsqlite.json'
api: /api/plugin/table/tables?path=notes/fsqlite.json
status: 200
{
  "type": "table_list",
  "path": "notes/fsqlite.json",
  "generation": "2-[..]",
  "tables": [
    {
      "id": "applied_tx",
      "label": "applied_tx",
      "group": "internal",
      "keyed": true,
      "estimate": 1,
      "path": "notes/fsqlite.json/applied_tx"
    },
    {
      "id": "fsqlite_meta",
      "label": "fsqlite_meta",
      "group": "internal",
      "keyed": true,
      "estimate": 4,
      "path": "notes/fsqlite.json/fsqlite_meta"
    },
    {
      "id": "notes",
      "label": "notes",
      "group": "tables",
      "keyed": true,
      "estimate": 2,
      "path": "notes/fsqlite.json/notes"
    }
  ]
}
? 0
```

```console
$ metab storeroot --show notes/fsqlite.json/notes
show: notes/fsqlite.json/notes
route: /view/notes/fsqlite.json/notes
kind: sqlite-store
views: table (default, key V), schema (key S), info (key I)
model: text envelope; size=0 content_bytes=0 content_truncated=False container=notes/fsqlite.json inner=notes
? 0
```

```console
$ metab storeroot --api '/api/plugin/table/rows?path=notes/fsqlite.json/notes'
api: /api/plugin/table/rows?path=notes/fsqlite.json/notes
status: 200
{
  "type": "table_rows",
  "path": "notes/fsqlite.json/notes",
  "table": "notes",
  "generation": "2-[..]",
  "columns": [
    "id",
    "title"
  ],
  "rows": [
    {
      "key": "k.WzFd",
      "cells": {
        "id": 1,
        "title": "first"
      }
    },
    {
      "key": "k.WzJd",
      "cells": {
        "id": 2,
        "title": "second"
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 2,
  "count_complete": true,
  "estimate": 2,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

```console
$ metab storeroot --api '/api/plugin/table/schema?path=notes/fsqlite.json/notes' > notes-schema.json
? 0
```

```console
$ grep -E '"(name|type|key)"' notes-schema.json
  "type": "table_schema",
  "key": [
      "name": "id",
      "type": "integer",
      "key": true,
      "name": "title",
      "type": "text",
      "key": false,
? 0
```

An internal table is listed and read like any other.

```console
$ metab storeroot --api '/api/plugin/table/rows?path=notes/fsqlite.json/applied_tx'
api: /api/plugin/table/rows?path=notes/fsqlite.json/applied_tx
status: 200
{
  "type": "table_rows",
  "path": "notes/fsqlite.json/applied_tx",
  "table": "applied_tx",
  "generation": "2-[..]",
  "columns": [
    "tx_id",
    "applied_at"
  ],
  "rows": [
    {
      "key": "k.WzFd",
      "cells": {
        "tx_id": "000000000001-000000000001-fixture-0123456789",
        "applied_at": "2026-11-20T00:00:00Z"
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 1,
  "count_complete": true,
  "estimate": 1,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

The Schema view’s route answers as the SQLite plugin’s does for a database, for the
whole snapshot or for the one table its address names.

```console
$ metab storeroot --api '/api/plugin/fsqlite/schema?path=notes/fsqlite.json/notes'
api: /api/plugin/fsqlite/schema?path=notes/fsqlite.json/notes
status: 200
{
  "type": "fsqlite_schema",
  "path": "notes/fsqlite.json/notes",
  "generation": "2-[..]",
  "objects": [
    {
      "type": "table",
      "name": "notes",
      "table": "notes",
      "sql": "CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL)",
      "segment": "notes"
    }
  ],
  "foreign_keys": [],
  "table": "notes"
}
? 0
```

```console
$ metab storeroot --api '/api/plugin/fsqlite/schema?path=notes/fsqlite.json/absent'
api: /api/plugin/fsqlite/schema?path=notes/fsqlite.json/absent
status: 404
{
  "type": "fsqlite_error",
  "path": "notes/fsqlite.json/absent",
  "code": "table_not_found",
  "error": "no table 'absent' in this store"
}
Error: /api/plugin/fsqlite/schema?path=notes/fsqlite.json/absent returned HTTP 404
? 1
```

A snapshot opened by itself is a database, and its `application_id` groups the reserved
tables as internal there too.

```console
$ metab storeroot --api '/api/plugin/table/tables?path=notes/snapshots/000000000002.fsqlite.sqlite' > snapshot-tables.json
? 0
```

```console
$ grep -E '"(id|group)"' snapshot-tables.json
      "id": "applied_tx",
      "group": "internal",
      "id": "fsqlite_meta",
      "group": "internal",
      "id": "notes",
      "group": "tables",
? 0
```

## Test: a store that cannot be shown says which state it is in

A pointer that is not ASCII digits is corrupt, never version 0.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=torn/fsqlite.json'
api: /api/plugin/fsqlite/info?path=torn/fsqlite.json
status: 200
{
  "type": "fsqlite_info",
  "path": "torn/fsqlite.json",
  "generation": null,
  "store": {
    "format_version": "f1.0",
    "store_id": "550e8400-e29b-41d4-a716-446655440000",
    "required_features": [],
    "pending": {
      "committed": 0,
      "uncommitted": 0,
      "complete": true
    }
  },
  "error": {
    "state": "corrupt",
    "message": "The current pointer does not name a version: “one”."
  }
}
? 0
```

A pointer that names a snapshot garbage collection has removed is read again once; one
that still names a missing snapshot is corrupt.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=collected/fsqlite.json' > collected.json
? 0
```

```console
$ grep -A3 '"error"' collected.json
  "error": {
    "state": "corrupt",
    "message": "The current pointer names version 5, whose snapshot 000000000005.fsqlite.sqlite is missing."
  }
? 0
```

A marker naming a format version this reader does not know is unsupported, not corrupt,
and nothing past it is read.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=newer/fsqlite.json'
api: /api/plugin/fsqlite/info?path=newer/fsqlite.json
status: 200
{
  "type": "fsqlite_info",
  "path": "newer/fsqlite.json",
  "generation": null,
  "store": {},
  "error": {
    "state": "unsupported",
    "message": "This store's format f2.0 is newer than this reader knows."
  }
}
? 0
```

A snapshot without fsqlite’s `application_id` is corrupt.
Info shows the store error.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=foreign/fsqlite.json' > foreign.json
? 0
```

```console
$ grep -A3 '"error"' foreign.json
  "error": {
    "state": "corrupt",
    "message": "The snapshot's application_id is 0x00000000, not fsqlite's 0x4653514c (“FSQL”)."
  }
? 0
```

```console
$ metab storeroot --api '/api/plugin/fsqlite/children?path=torn/fsqlite.json'
api: /api/plugin/fsqlite/children?path=torn/fsqlite.json
status: 200
{
  "children": [],
  "error": {
    "state": "corrupt",
    "message": "The current pointer does not name a version: “one”."
  }
}
? 0
```

The table routes refuse a store they cannot read, naming the same state.

```console
$ metab storeroot --api '/api/plugin/table/tables?path=newer/fsqlite.json'
api: /api/plugin/table/tables?path=newer/fsqlite.json
status: 422
{
  "type": "table_error",
  "path": "newer/fsqlite.json",
  "code": "source_unreadable",
  "error": "This store's format f2.0 is newer than this reader knows.",
  "state": "unsupported"
}
Error: /api/plugin/table/tables?path=newer/fsqlite.json returned HTTP 422
? 1
```

```console
$ metab storeroot --api '/api/plugin/table/rows?path=collected/fsqlite.json/notes'
api: /api/plugin/table/rows?path=collected/fsqlite.json/notes
status: 422
{
  "type": "table_error",
  "path": "collected/fsqlite.json/notes",
  "code": "source_unreadable",
  "error": "The current pointer names version 5, whose snapshot 000000000005.fsqlite.sqlite is missing.",
  "state": "corrupt"
}
Error: /api/plugin/table/rows?path=collected/fsqlite.json/notes returned HTTP 422
? 1
```

A path that is not a store’s marker is not found.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=notes/current'
api: /api/plugin/fsqlite/info?path=notes/current
status: 404
{
  "type": "fsqlite_error",
  "path": "notes/current",
  "code": "not_found",
  "error": "This is not an fsqlite store's marker."
}
Error: /api/plugin/fsqlite/info?path=notes/current returned HTTP 404
? 1
```

## Test: reading a store changes nothing in it

No lease, no lock, and no file beside a snapshot: after every read above, the Info,
Schema, and children hooks and the table routes alike, every entry and every byte is as
the `before:` script left it.

```console
$ find storeroot | LC_ALL=C sort | diff listing-before.txt - && find storeroot -type f -exec cksum {} + | LC_ALL=C sort | diff sums-before.txt - && echo unchanged
unchanged
? 0
```
