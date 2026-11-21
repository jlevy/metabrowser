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
  PYTHONPATH="$TRYSCRIPT_TEST_DIR/../.."
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python -m tests.sqlite_golden_fixture sqlroot
  > fixture.log 2>&1
---
# Golden tests: SQLite databases, read as a guest

The built-in `sqlite` plugin claims any SQLite database by the 16 bytes it starts with,
whatever its name, and shows its Info view from `/api/plugin/sqlite/info`. Every
connection runs in a reader process, through `metabrowser.sqlite_access`, which chooses
how to open each database from what it finds beside it, and never writes to it or leaves
a file beside it. The databases are built from SQL text in
`tests/sqlite_guest_scenarios.py` and `tests/sqlite_golden_fixture.py`, with their
owners in processes of their own.

A generation names a file’s identity and time, and the library block names the SQLite
this interpreter loads and which of the releases it lists that library includes, so the
transcripts elide those, and after the first stop before the library block.

## Test: a database is claimed by its magic number, whatever its name

```console
$ metab sqlroot --show app.db
show: app.db
route: /view/app.db
kind: sqlite
views: table (default, key V), schema (key S), info (key I)
model: binary envelope; size=16384
? 0
```

## Test: a rollback-journal database is read without a lock

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=app.db'
api: /api/plugin/sqlite/info?path=app.db
status: 200
{
  "type": "sqlite_info",
  "path": "app.db",
  "generation": "[..]",
  "access": {
    "mode": "immutable",
    "state": "current",
    "reason": "a rollback-journal database is read without a lock, validated against a commit",
    "attempts": 1,
    "notices": []
  },
  "journal_mode": "rollback",
  "links": 1,
  "size": 16384,
  "sidecars": [],
  "database": {
    "page_size": 4096,
    "page_count": 4,
    "encoding": "UTF-8",
    "user_version": 3,
    "application_id": 1179865420,
    "application_name": "fsqlite snapshot",
    "freelist_count": 0,
    "objects": {
      "index": 1,
      "table": 2,
      "trigger": 1,
      "view": 1
    }
  },
  "library": {
    "version": "[..]",
    "minimum": "3.43.0",
    "meets_minimum": [..],
    "versions": [
      {
        "version": "3.7.0",
        "meaning": "write-ahead-log databases",
        "available": [..]
      },
      {
        "version": "3.8.2",
        "meaning": "WITHOUT ROWID tables",
        "available": [..]
      },
      {
        "version": "3.26.0",
        "meaning": "SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
        "available": [..]
      },
      {
        "version": "3.31.0",
        "meaning": "PRAGMA trusted_schema and generated columns",
        "available": [..]
      },
      {
        "version": "3.37.0",
        "meaning": "STRICT tables",
        "available": [..]
      },
      {
        "version": "3.43.0",
        "meaning": "octet_length(), the reader's minimum for reading tables",
        "available": [..]
      },
      {
        "version": "3.45.0",
        "meaning": "JSONB values",
        "available": [..]
      }
    ]
  }
}
? 0
```

A database with no extension, and one with an extension no rule lists, are claimed the
same way; a `.db` file that is not SQLite stays binary, and so does a compressed
database, since the magic number is checked on the bytes on disk.

```console
$ metab sqlroot --show History
show: History
route: /view/History
kind: sqlite
views: table (default, key V), schema (key S), info (key I)
model: binary envelope; size=8192
? 0
```

```console
$ metab sqlroot --show notes.dat
show: notes.dat
route: /view/notes.dat
kind: sqlite
views: table (default, key V), schema (key S), info (key I)
model: binary envelope; size=8192
? 0
```

```console
$ metab sqlroot --show fake.db
show: fake.db
route: /view/fake.db
kind: binary
views: bytes (default)
model: binary envelope; size=45
? 0
```

```console
$ metab sqlroot --show packed.sqlite.gz
show: packed.sqlite.gz
route: /view/packed.sqlite.gz
kind: binary
views: bytes (default)
model: binary envelope; size=169
? 0
```

## Test: an idle write-ahead-log database is read without a lock, creating nothing

Its log holds no frames, so the main file is read with `immutable=1`; opening it with
`mode=ro` would leave a `-wal` and a `-shm` beside it.

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=History' > history.txt
? 0
```

```console
$ sed '/"library"/,$d' history.txt
api: /api/plugin/sqlite/info?path=History
status: 200
{
  "type": "sqlite_info",
  "path": "History",
  "generation": "[..]",
  "access": {
    "mode": "immutable",
    "state": "current",
    "reason": "the write-ahead log holds no frames, so the main file is read without a lock, validated against a new frame or checkpoint",
    "attempts": 1,
    "notices": []
  },
  "journal_mode": "wal",
  "links": 1,
  "size": 8192,
  "sidecars": [],
  "database": {
    "page_size": 4096,
    "page_count": 2,
    "encoding": "UTF-8",
    "user_version": 0,
    "application_id": 0,
    "application_name": null,
    "freelist_count": 0,
    "objects": {
      "table": 1
    }
  },
? 0
```

## Test: a crashed owner’s log is read through a private copy, its index untouched

The owner committed five rows to its log and was killed, leaving `-wal` and `-shm`. No
process holds the index, so opening it in place would rebuild it by rewriting `-shm`;
the database and its log are copied to a private folder and read there, and `-shm` keeps
its bytes.

```console
$ cksum < sqlroot/live.db-shm > shm-before.txt
? 0
```

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=live.db' > live.txt
? 0
```

```console
$ cksum < sqlroot/live.db-shm | diff - shm-before.txt
? 0
```

```console
$ sed '/"library"/,$d' live.txt
api: /api/plugin/sqlite/info?path=live.db
status: 200
{
  "type": "sqlite_info",
  "path": "live.db",
  "generation": "[..]",
  "access": {
    "mode": "private_copy",
    "state": "current",
    "reason": "the write-ahead log holds frames and no application has it open, so the database and its log are read through a private copy",
    "attempts": 1,
    "notices": []
  },
  "journal_mode": "wal",
  "links": 1,
  "size": 8192,
  "sidecars": [
    {
      "name": "-wal",
      "size": 20632,
      "frames": 5
    },
    {
      "name": "-shm",
      "size": 32768
    }
  ],
  "database": {
    "page_size": 4096,
    "page_count": 2,
    "encoding": "UTF-8",
    "user_version": 0,
    "application_id": 0,
    "application_name": null,
    "freelist_count": 0,
    "objects": {
      "table": 1
    }
  },
? 0
```

## Test: a log with no index beside it is read through a private copy

Opening it in place would create a `-shm` beside it, so the database and its log are
copied to a private folder and read there.

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=copied.sqlite3' > copied.txt
? 0
```

```console
$ sed '/"library"/,$d' copied.txt
api: /api/plugin/sqlite/info?path=copied.sqlite3
status: 200
{
  "type": "sqlite_info",
  "path": "copied.sqlite3",
  "generation": "[..]",
  "access": {
    "mode": "private_copy",
    "state": "current",
    "reason": "the write-ahead log holds frames and has no index beside it, so the database and its log are read through a private copy",
    "attempts": 1,
    "notices": []
  },
  "journal_mode": "wal",
  "links": 1,
  "size": 8192,
  "sidecars": [
    {
      "name": "-wal",
      "size": 20632,
      "frames": 5
    }
  ],
  "database": {
    "page_size": 4096,
    "page_count": 2,
    "encoding": "UTF-8",
    "user_version": 0,
    "application_id": 0,
    "application_name": null,
    "freelist_count": 0,
    "objects": {
      "table": 1
    }
  },
? 0
```

## Test: a crafted schema’s object types are counted, not listed

SQLite accepts a schema row whose type reads as `table` up to a NUL; the fixture has
forty with forty suffixes, and one whose type is a blob.
They are counted as `other`.

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=crafted.db' > crafted.txt
? 0
```

```console
$ sed -n '/"objects"/,/}/p' crafted.txt
    "objects": {
      "other": 41,
      "table": 1
    }
? 0
```

## Test: the library block names the reader’s minimum

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=app.db' > library.txt
? 0
```

```console
$ grep -E '"(minimum|meaning)"' library.txt
    "minimum": "3.43.0",
        "meaning": "write-ahead-log databases",
        "meaning": "WITHOUT ROWID tables",
        "meaning": "SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo",
        "meaning": "PRAGMA trusted_schema and generated columns",
        "meaning": "STRICT tables",
        "meaning": "octet_length(), the reader's minimum for reading tables",
        "meaning": "JSONB values",
? 0
```

## Test: what cannot be read says why

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=fake.db'
api: /api/plugin/sqlite/info?path=fake.db
status: 200
{
  "type": "sqlite_info",
  "path": "fake.db",
  "generation": "[..]",
  "error": {
    "state": "not_sqlite",
    "message": "This file is not a SQLite database."
  }
}
? 0
```

```console
$ metab sqlroot --api '/api/plugin/sqlite/info?path=missing.db'
api: /api/plugin/sqlite/info?path=missing.db
status: 404
{
  "type": "sqlite_error",
  "path": "missing.db",
  "code": "not_found",
  "error": "Not found"
}
Error: /api/plugin/sqlite/info?path=missing.db returned HTTP 404
? 1
```

## Test: no read left a file beside a database

```console
$ ls sqlroot
History
app.db
copied.sqlite3
copied.sqlite3-wal
crafted.db
fake.db
live.db
live.db-shm
live.db-wal
notes.dat
packed.sqlite.gz
? 0
```
