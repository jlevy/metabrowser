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
views: info (default)
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

## Test: the children hook answers in its shape

The store is a container whose children are its snapshot’s tables.
The SQLite source that lists them joins this hook later in the stack, so it answers none
yet, with the snapshot it read.

```console
$ metab storeroot --api '/api/plugin/fsqlite/children?path=notes/fsqlite.json'
api: /api/plugin/fsqlite/children?path=notes/fsqlite.json
status: 200
{
  "children": [],
  "version": 2,
  "snapshot": "000000000002.fsqlite.sqlite"
}
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

A snapshot without fsqlite’s `application_id` is shown, and the store is corrupt.

```console
$ metab storeroot --api '/api/plugin/fsqlite/info?path=foreign/fsqlite.json' > foreign.json
? 0
```

```console
$ grep -E -A3 '"(error|application_name)"' foreign.json
      "application_name": null,
      "freelist_count": 0,
      "objects": {
        "index": 2,
--
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

No lease, no lock, and no file beside a snapshot: every entry and every byte is as the
`before:` script left it.

```console
$ find storeroot | LC_ALL=C sort | diff listing-before.txt - && find storeroot -type f -exec cksum {} + | LC_ALL=C sort | diff sums-before.txt - && echo unchanged
unchanged
? 0
```
