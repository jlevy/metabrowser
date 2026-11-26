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
  mkdir -p dbroot &&
  for name in app big; do
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../sqlite_fixture.py"
  "dbroot/$name.db" "$TRYSCRIPT_TEST_DIR/../fixtures/sqlite-tables/$name.sql" || exit 1;
  done &&
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../sqlite_fixture.py"
  dbroot/History "$TRYSCRIPT_TEST_DIR/../fixtures/sqlite-tables/snapshot.sql" &&
  printf 'not a database\000\001\002' > dbroot/fake.db
---
# Golden tests: a SQLite database’s tables through the table routes

A SQLite database is a navigation container: its tables, views, and virtual tables are
its children, each at `<database>/<segment>`, and the table routes serve each one
through the `sqlite` plugin’s `[[table_source]]`, which reads in a reader process
without changing the file.
The databases are built in this file’s `before:` script from the SQL under
`tests/fixtures/sqlite-tables/`, not from committed binaries.
A generation is the file’s identity, size, modification time, and header, so it differs
from one build to the next and the transcripts elide it.

## Test: a database, a table inside it, and a database with no extension

The database and each table share the `sqlite` kind and its views; a table’s address
extends its database’s, and a name a path segment cannot carry as it is, such as one
with a space, is `~` and the hexadecimal of its bytes.
A database is claimed by its first bytes whatever its name, and a `.db` file that is not
one stays binary.

```console
$ metab dbroot --show app.db
show: app.db
route: /view/app.db
kind: sqlite
views: table (default, key V), schema (key S), info (key I)
model: binary envelope; size=[..]
? 0
```

```console
$ metab dbroot --show app.db/~6f72646572206974656d73
show: app.db/~6f72646572206974656d73
route: /view/app.db/~6f72646572206974656d73
kind: sqlite
views: table (default, key V), schema (key S), info (key I)
model: text envelope; size=0 content_bytes=0 content_truncated=False container=app.db inner=~6f72646572206974656d73
? 0
```

```console
$ metab dbroot --show History/items
show: History/items
route: /view/History/items
kind: sqlite
views: table (default, key V), schema (key S), info (key I)
model: text envelope; size=0 content_bytes=0 content_truncated=False container=History inner=items
? 0
```

```console
$ metab dbroot --show fake.db
show: fake.db
route: /view/fake.db
kind: binary
views: bytes (default)
model: binary envelope; size=17
? 0
```

## Test: the tables, by group, with their estimates

Tables, views, virtual tables, and internal ones (`sqlite_sequence`, a virtual table’s
shadow tables, and an fsqlite snapshot’s reserved tables) each have a group.
An estimate is cheap: the largest rowid, or `ANALYZE`’s count, never a count.
A table whose rows have no key is named by position, as a view’s rows are.

```console
$ metab dbroot --api '/api/plugin/table/tables?path=app.db' > answer-1.txt
? 0
```

```console
$ grep -E '"(id|label|group|keyed|estimate)"' answer-1.txt
      "id": "blobs",
      "label": "blobs",
      "group": "tables",
      "keyed": true,
      "estimate": 3,
      "id": "counters",
      "label": "counters",
      "group": "tables",
      "keyed": true,
      "estimate": 2,
      "id": "~67312d6c696b65",
      "label": "g1-like",
      "group": "tables",
      "keyed": true,
      "estimate": 0,
      "id": "grants",
      "label": "grants",
      "group": "tables",
      "keyed": true,
      "estimate": 3,
      "id": "huge",
      "label": "huge",
      "group": "tables",
      "keyed": true,
      "estimate": 2,
      "id": "notes",
      "label": "notes",
      "group": "virtual",
      "keyed": false,
      "estimate": null,
      "id": "notes_config",
      "label": "notes_config",
      "group": "internal",
      "keyed": false,
      "estimate": null,
      "id": "notes_content",
      "label": "notes_content",
      "group": "internal",
      "keyed": false,
      "estimate": null,
      "id": "notes_data",
      "label": "notes_data",
      "group": "internal",
      "keyed": false,
      "estimate": null,
      "id": "notes_docsize",
      "label": "notes_docsize",
      "group": "internal",
      "keyed": false,
      "estimate": null,
      "id": "notes_idx",
      "label": "notes_idx",
      "group": "internal",
      "keyed": false,
      "estimate": null,
      "id": "~6f72646572206974656d73",
      "label": "order items",
      "group": "tables",
      "keyed": true,
      "estimate": 1,
      "id": "orders",
      "label": "orders",
      "group": "tables",
      "keyed": true,
      "estimate": 5,
      "id": "prices",
      "label": "prices",
      "group": "tables",
      "keyed": true,
      "estimate": 2,
      "id": "shadows",
      "label": "shadows",
      "group": "tables",
      "keyed": false,
      "estimate": 2,
      "id": "shouting",
      "label": "shouting",
      "group": "views",
      "keyed": false,
      "estimate": null,
      "id": "sqlite_sequence",
      "label": "sqlite_sequence",
      "group": "internal",
      "keyed": true,
      "estimate": 1,
      "id": "tags",
      "label": "tags",
      "group": "tables",
      "keyed": true,
      "estimate": 3,
      "id": "users",
      "label": "users",
      "group": "tables",
      "keyed": true,
      "estimate": 6,
      "id": "~7e74696c6465",
      "label": "~tilde",
      "group": "tables",
      "keyed": true,
      "estimate": 0,
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/tables?path=History' > answer-2.txt
? 0
```

```console
$ grep -E '"(label|group)"' answer-2.txt
      "label": "applied_tx",
      "group": "internal",
      "label": "fsqlite_meta",
      "group": "internal",
      "label": "items",
      "group": "tables",
? 0
```

The tree’s rows for the container are the same tables, each at its address; internal
tables are muted and views badged.
A file the kind’s extensions name that is not a database has none.

```console
$ metab dbroot --api '/api/plugin/sqlite/children?path=app.db'
api: /api/plugin/sqlite/children?path=app.db
status: 200
{
  "children": [
    {
      "name": "blobs",
      "path": "app.db/blobs"
    },
    {
      "name": "counters",
      "path": "app.db/counters"
    },
    {
      "name": "g1-like",
      "path": "app.db/~67312d6c696b65"
    },
    {
      "name": "grants",
      "path": "app.db/grants"
    },
    {
      "name": "huge",
      "path": "app.db/huge"
    },
    {
      "name": "notes",
      "path": "app.db/notes",
      "badge": "VT"
    },
    {
      "name": "notes_config",
      "path": "app.db/notes_config",
      "muted": true
    },
    {
      "name": "notes_content",
      "path": "app.db/notes_content",
      "muted": true
    },
    {
      "name": "notes_data",
      "path": "app.db/notes_data",
      "muted": true
    },
    {
      "name": "notes_docsize",
      "path": "app.db/notes_docsize",
      "muted": true
    },
    {
      "name": "notes_idx",
      "path": "app.db/notes_idx",
      "muted": true
    },
    {
      "name": "order items",
      "path": "app.db/~6f72646572206974656d73"
    },
    {
      "name": "orders",
      "path": "app.db/orders"
    },
    {
      "name": "prices",
      "path": "app.db/prices"
    },
    {
      "name": "shadows",
      "path": "app.db/shadows"
    },
    {
      "name": "shouting",
      "path": "app.db/shouting",
      "badge": "V"
    },
    {
      "name": "sqlite_sequence",
      "path": "app.db/sqlite_sequence",
      "muted": true
    },
    {
      "name": "tags",
      "path": "app.db/tags"
    },
    {
      "name": "users",
      "path": "app.db/users"
    },
    {
      "name": "~tilde",
      "path": "app.db/~7e74696c6465"
    }
  ]
}
? 0
```

```console
$ metab dbroot --api '/api/plugin/sqlite/children?path=fake.db'
api: /api/plugin/sqlite/children?path=fake.db
status: 200
{
  "children": []
}
? 0
```

## Test: a table’s fields, keys, and references

Types come from the declared types: `BOOLEAN`, `DATE`, and `JSON` are named, and a blob
does not filter. `users` is keyed by its integer primary key, and the foreign key from
`orders` is a back-reference here.

```console
$ metab dbroot --api '/api/plugin/table/schema?path=app.db/users' > users-schema.txt
? 0
```

```console
$ grep -E '^  "(table|key|path)":|^      "(name|type|declared_type|sortable|filterable)":' users-schema.txt
  "path": "app.db/users",
  "table": "users",
  "key": [
      "name": "id",
      "type": "integer",
      "declared_type": "INTEGER",
      "sortable": true,
      "filterable": true,
      "name": "name",
      "type": "text",
      "declared_type": "TEXT",
      "sortable": true,
      "filterable": true,
      "name": "email",
      "type": "text",
      "declared_type": "TEXT",
      "sortable": true,
      "filterable": true,
      "name": "age",
      "type": "integer",
      "declared_type": "INTEGER",
      "sortable": true,
      "filterable": true,
      "name": "active",
      "type": "boolean",
      "declared_type": "BOOLEAN",
      "sortable": true,
      "filterable": true,
      "name": "joined",
      "type": "date",
      "declared_type": "DATE",
      "sortable": true,
      "filterable": true,
      "name": "prefs",
      "type": "json",
      "declared_type": "JSON",
      "sortable": true,
      "filterable": true,
      "name": "avatar",
      "type": "blob",
      "declared_type": "BLOB",
      "sortable": true,
      "filterable": false,
      "name": "bio",
      "type": "text",
      "declared_type": "TEXT",
      "sortable": true,
      "filterable": true,
? 0
```

```console
$ grep -A8 '"referenced_by"' users-schema.txt
  "referenced_by": [
    {
      "table": "orders",
      "fields": [
        "user_id"
      ],
      "to": [
        "id"
      ]
? 0
```

`orders` has no integer primary key, so its key is the hidden `rowid`, which no default
column shows; `grants` names a `WITHOUT ROWID` table through a composite foreign key,
one reference over two fields.

```console
$ metab dbroot --api '/api/plugin/table/schema?path=app.db/orders' > answer-4.txt
? 0
```

```console
$ grep -E -A10 '^  "key"' answer-4.txt
  "key": [
    "rowid"
  ],
  "default_columns": [
    "user_id",
    "total",
    "note"
  ],
  "fields": [
    {
      "name": "rowid",
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/schema?path=app.db/grants'
api: /api/plugin/table/schema?path=app.db/grants
status: 200
{
  "type": "table_schema",
  "path": "app.db/grants",
  "table": "grants",
  "generation": "[..]",
  "key": [
    "id"
  ],
  "default_columns": [
    "id",
    "owner",
    "tag"
  ],
  "fields": [
    {
      "name": "id",
      "title": null,
      "type": "integer",
      "declared_type": "INTEGER",
      "nullable": false,
      "key": true,
      "hidden": false,
      "generated": false,
      "list": false,
      "enum": null,
      "format": null,
      "ref": null,
      "sortable": true,
      "sort_note": null,
      "filterable": true,
      "numeric": true
    },
    {
      "name": "owner",
      "title": null,
      "type": "integer",
      "declared_type": "INTEGER",
      "nullable": true,
      "key": false,
      "hidden": false,
      "generated": false,
      "list": false,
      "enum": null,
      "format": null,
      "ref": {
        "table": "tags",
        "fields": [
          "owner",
          "tag"
        ],
        "to": [
          "owner",
          "tag"
        ]
      },
      "sortable": true,
      "sort_note": null,
      "filterable": true,
      "numeric": true
    },
    {
      "name": "tag",
      "title": null,
      "type": "text",
      "declared_type": "TEXT",
      "nullable": true,
      "key": false,
      "hidden": false,
      "generated": false,
      "list": false,
      "enum": null,
      "format": null,
      "ref": {
        "table": "tags",
        "fields": [
          "owner",
          "tag"
        ],
        "to": [
          "owner",
          "tag"
        ]
      },
      "sortable": true,
      "sort_note": null,
      "filterable": true,
      "numeric": false
    }
  ],
  "references": [
    {
      "table": "tags",
      "fields": [
        "owner",
        "tag"
      ],
      "to": [
        "owner",
        "tag"
      ]
    }
  ],
  "referenced_by": []
}
? 0
```

Past `SORT_UNINDEXED_MAX_ROWS`, only the key and a field an index leads with sort; the
rest say why, and a sort of one is refused.

```console
$ metab dbroot --api '/api/plugin/table/schema?path=big.db/events' > answer-6.txt
? 0
```

```console
$ grep -E '"(name|sortable|sort_note)"' answer-6.txt
      "name": "id",
      "sortable": true,
      "sort_note": null,
      "name": "at",
      "sortable": true,
      "sort_note": null,
      "name": "kind",
      "sortable": false,
      "sort_note": "only indexed fields sort in an object of more than 100,000 rows: a sort of this field would read and sort every row first",
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/rows?path=big.db/events&sort=kind'
api: /api/plugin/table/rows?path=big.db/events&sort=kind
status: 400
{
  "type": "table_error",
  "path": "big.db/events",
  "code": "bad_query",
  "error": "field 'kind' is not sortable: only indexed fields sort in an object of more than 100,000 rows: a sort of this field would read and sort every row first",
  "param": "sort",
  "field": "kind"
}
Error: /api/plugin/table/rows?path=big.db/events&sort=kind returned HTTP 400
? 1
```

## Test: a page of typed cells

Every value is shown as stored: an integer past 2⁵³ keeps its digits, text in an integer
column says it is text, a boolean is `true` or `false`, JSON text is parsed, a blob is
hex with its size, text that is not valid UTF-8 is marked, and a value longer than a
page reads whole is previewed from its stored bytes with its size.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&cols=id&cols=age&cols=active&cols=prefs&cols=avatar&cols=bio' > answer-7.txt
? 0
```

```console
$ cut -c1-72 answer-7.txt
api: /api/plugin/table/rows?path=app.db/users&cols=id&cols=age&cols=acti
status: 200
{
  "type": "table_rows",
  "path": "app.db/users",
  "table": "users",
  "generation": "[..]",
  "columns": [
    "id",
    "age",
    "active",
    "prefs",
    "avatar",
    "bio"
  ],
  "rows": [
    {
      "key": "k.WzFd",
      "cells": {
        "id": 1,
        "age": 36,
        "active": true,
        "prefs": {
          "json": {
            "theme": "dark"
          },
          "preview": "{\"theme\":\"dark\"}"
        },
        "avatar": {
          "blob": true,
          "length": 3,
          "hex": "00ff10"
        },
        "bio": null
      }
    },
    {
      "key": "k.WzJd",
      "cells": {
        "id": 2,
        "age": {
          "value": "unknown",
          "stored": "text"
        },
        "active": false,
        "prefs": "not json",
        "avatar": null,
        "bio": ""
      }
    },
    {
      "key": "k.WzNd",
      "cells": {
        "id": 3,
        "age": {
          "int": "9007199254740993"
        },
        "active": true,
        "prefs": {
          "json": [
            1,
            2
          ],
          "preview": "[1,2]"
        },
        "avatar": null,
        "bio": {
          "text": "00000000000000000000000000000000000000000000000000000
          "bytes": 5200
        }
      }
    },
    {
      "key": "k.WzRd",
      "cells": {
        "id": 4,
        "age": {
          "int": "-9223372036854775808"
        },
        "active": {
          "value": 2,
          "stored": "integer"
        },
        "prefs": null,
        "avatar": {
          "blob": true,
          "length": 300,
          "hex": "000000000000000000000000000000000000000000000000000000
        },
        "bio": null
      }
    },
    {
      "key": "k.WzVd",
      "cells": {
        "id": 5,
        "age": 41,
        "active": true,
        "prefs": null,
        "avatar": null,
        "bio": {
          "text": "�A",
          "invalid_utf8": true
        }
      }
    },
    {
      "key": "k.WzZd",
      "cells": {
        "id": 6,
        "age": 29,
        "active": false,
        "prefs": null,
        "avatar": null,
        "bio": null
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 6,
  "count_complete": true,
  "estimate": 6,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

A reference is resolved for the whole page in one read: a value no row holds is drawn
missing, and an infinite real is `{real}`.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/orders'
api: /api/plugin/table/rows?path=app.db/orders
status: 200
{
  "type": "table_rows",
  "path": "app.db/orders",
  "table": "orders",
  "generation": "[..]",
  "columns": [
    "user_id",
    "total",
    "note"
  ],
  "rows": [
    {
      "key": "k.WzFd",
      "cells": {
        "user_id": {
          "ref": {
            "table": "users",
            "key": "k.WzFd",
            "label": 1
          }
        },
        "total": 9.5,
        "note": "first"
      }
    },
    {
      "key": "k.WzJd",
      "cells": {
        "user_id": {
          "ref": {
            "table": "users",
            "key": "k.WzFd",
            "label": 1
          }
        },
        "total": {
          "real": "inf"
        },
        "note": null
      }
    },
    {
      "key": "k.WzNd",
      "cells": {
        "user_id": {
          "ref": {
            "table": "users",
            "key": "k.WzJd",
            "label": 2
          }
        },
        "total": {
          "real": "-inf"
        },
        "note": "second"
      }
    },
    {
      "key": "k.WzRd",
      "cells": {
        "user_id": {
          "ref": {
            "table": "users",
            "key": null,
            "label": 99,
            "missing": true
          }
        },
        "total": 0.5,
        "note": "dangling"
      }
    },
    {
      "key": "k.WzVd",
      "cells": {
        "user_id": null,
        "total": null,
        "note": "no user"
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 5,
  "count_complete": true,
  "estimate": 5,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

## Test: paging in both directions, nulls first ascending and last descending

A sorted page reads the sort field’s nulls by key and its values by row value, each by
its own index seek, and its cursor names the region it stopped in.
Ascending, the nulls come first; descending, last.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&sort=email&cols=email&limit=3' > answer-8.txt
? 0
```

```console
$ grep -E '"(email|next_after|count)"' answer-8.txt
    "email"
        "email": null
        "email": null
        "email": "7"
  "next_after": "c.WyJlbWFpbCIsImFzYyIsInYiLCI3IixbNl0sM10",
  "count": 6,
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&sort=email&order=desc&cols=email&limit=3'
api: /api/plugin/table/rows?path=app.db/users&sort=email&order=desc&cols=email&limit=3
status: 200
{
  "type": "table_rows",
  "path": "app.db/users",
  "table": "users",
  "generation": "[..]",
  "columns": [
    "email"
  ],
  "rows": [
    {
      "key": "k.WzNd",
      "cells": {
        "email": "cy@example.com"
      }
    },
    {
      "key": "k.WzFd",
      "cells": {
        "email": "ada@example.com"
      }
    },
    {
      "key": "k.WzVd",
      "cells": {
        "email": "EVE@example.com"
      }
    }
  ],
  "next_after": "c.WyJlbWFpbCIsImRlc2MiLCJ2IiwiRVZFQGV4YW1wbGUuY29tIixbNV0sM10",
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 6,
  "count_complete": true,
  "estimate": 6,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 3
}
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&sort=email&order=desc&cols=email&limit=3&after=c.WyJlbWFpbCIsImRlc2MiLCJ2IiwiRVZFQGV4YW1wbGUuY29tIixbNV0sM10' > answer-10.txt
? 0
```

```console
$ grep -E '"(email|next_after)"' answer-10.txt
    "email"
        "email": "7"
        "email": null
        "email": null
  "next_after": "c.WyJlbWFpbCIsImRlc2MiLCJuIixudWxsLFsyXSw2XQ",
? 0
```

A cursor made for another sort is refused by name.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&sort=age&after=c.WyJlbWFpbCIsImRlc2MiLCJ2IiwiRVZFQGV4YW1wbGUuY29tIixbNV0sM10' > answer-11.txt
Error: /api/plugin/table/rows?path=app.db/users&sort=age&after=c.WyJlbWFpbCIsImRlc2MiLCJ2IiwiRVZFQGV4YW1wbGUuY29tIixbNV0sM10 returned HTTP 400
? 1
```

```console
$ grep -E '"(code|error)"' answer-11.txt
  "code": "bad_query",
  "error": "after is not a cursor for this query: it was made for sort=\"email\" order=\"desc\"",
? 0
```

An indexed sort of a table past the unindexed bound is a seek, and its count is exact up
to `COUNT_CAP`.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=big.db/events&sort=at&order=desc&cols=at&limit=2' > answer-12.txt
? 0
```

```console
$ grep -E '"(key|at|next_after|count|count_complete)"' answer-12.txt
    "at"
      "key": "k.Wzk5Njk5XQ",
        "at": 996
      "key": "k.Wzk4NzAyXQ",
        "at": 996
  "next_after": "c.WyJhdCIsImRlc2MiLCJ2Iiw5OTYsWzk4NzAyXSwyXQ",
  "count": 100001,
  "count_complete": true,
? 0
```

A view has no key, so its rows are named by their position in its own order, and a view
that calls built-in functions reads under the reads-only authorizer.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/shouting&order=desc&limit=2' > answer-13.txt
? 0
```

```console
$ grep -E '"(key|name|letters)"' answer-13.txt
    "name",
    "letters"
      "key": "@6",
        "name": "FAY",
        "letters": 3
      "key": "@5",
        "name": "EVE",
        "letters": 3
? 0
```

## Test: filters, search, and the rows that reference a record

An order filter compares values of its own kind; a search looks in text fields and says
which; `ref=` keeps the rows that reference one record.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&f.age=gt:35&cols=name' > answer-14.txt
? 0
```

```console
$ grep -E '"(name|count)"' answer-14.txt
    "name"
        "name": "Ada"
        "name": "Cy"
        "name": "Eve"
  "count": 3,
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/users&q=EXAMPLE&cols=email' > answer-15.txt
? 0
```

```console
$ grep -E -A4 '"(email|searched)"' answer-15.txt
    "email"
  ],
  "rows": [
    {
      "key": "k.WzFd",
--
        "email": "ada@example.com"
      }
    },
    {
      "key": "k.WzNd",
--
        "email": "cy@example.com"
      }
    },
    {
      "key": "k.WzVd",
--
        "email": "EVE@example.com"
      }
    }
  ],
  "next_after": null,
--
  "searched": [
    "name",
    "email",
    "bio"
  ],
  "sort_refused": null,
  "limit": 100
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/orders&ref=users:k.WzFd' > answer-16.txt
? 0
```

```console
$ grep -E '"(note|count)"' answer-16.txt
    "note"
        "note": "first"
        "note": null
  "count": 2,
? 0
```

The declared field pair names the same rows when it is the table’s only relationship.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/orders&ref=users:k.WzFd&via=%5B%5B%22user_id%22%5D%2C%5B%22id%22%5D%5D' > scoped-16.txt
? 0
```

```console
$ grep -E '"(note|count)"' scoped-16.txt
    "note"
        "note": "first"
        "note": null
  "count": 2,
? 0
```

A value past the reader’s length limit is not examined, and the page counts it.

```console
$ metab dbroot --api '/api/plugin/table/rows?path=app.db/huge&q=small' > answer-17.txt
? 0
```

```console
$ grep -E '"(body|skipped)"' answer-17.txt
    "body"
        "body": "small"
  "skipped": 1,
    "body"
? 0
```

## Test: one record, and a hover card

A record previews each value past the record bound and counts the rows of each table
that reference it.

```console
$ metab dbroot --api '/api/plugin/table/record?path=app.db/users&key=k.WzFd'
api: /api/plugin/table/record?path=app.db/users&key=k.WzFd
status: 200
{
  "type": "table_record",
  "path": "app.db/users",
  "table": "users",
  "key": "k.WzFd",
  "positional": false,
  "generation": "[..]",
  "generation_moved": null,
  "cells": {
    "id": 1,
    "name": "Ada",
    "email": "ada@example.com",
    "age": 36,
    "active": true,
    "joined": "2020-01-02",
    "prefs": {
      "json": {
        "theme": "dark"
      },
      "preview": "{\"theme\":\"dark\"}"
    },
    "avatar": {
      "blob": true,
      "length": 3,
      "hex": "00ff10"
    },
    "bio": null
  },
  "label": "Ada",
  "referenced_by": [
    {
      "table": "orders",
      "fields": [
        "user_id"
      ],
      "to": [
        "id"
      ],
      "count": 2,
      "count_complete": true
    }
  ]
}
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/card?path=app.db/grants&key=k.WzFd'
api: /api/plugin/table/card?path=app.db/grants&key=k.WzFd
status: 200
{
  "type": "table_card",
  "path": "app.db/grants",
  "table": "grants",
  "key": "k.WzFd",
  "generation": "[..]",
  "label": {
    "ref": {
      "table": "tags",
      "key": "k.WzEsImFkbWluIl0",
      "label": "ADMIN"
    }
  },
  "cells": {
    "id": 1,
    "owner": {
      "ref": {
        "table": "tags",
        "key": "k.WzEsImFkbWluIl0",
        "label": 1
      }
    }
  }
}
? 0
```

```console
$ metab dbroot --api '/api/plugin/table/record?path=app.db/users&key=k.Wzk5OV0' > answer-18.txt
Error: /api/plugin/table/record?path=app.db/users&key=k.Wzk5OV0 returned HTTP 404
? 1
```

```console
$ grep -E '"(code|error)"' answer-18.txt
  "code": "record_not_found",
  "error": "'k.Wzk5OV0' names no row of this table",
? 0
```

## Test: the Schema view’s model

Each object’s DDL, with its indexes and triggers, and every table’s foreign keys; at a
table’s address, that table’s alone.

```console
$ metab dbroot --api '/api/plugin/sqlite/schema?path=app.db/grants'
api: /api/plugin/sqlite/schema?path=app.db/grants
status: 200
{
  "type": "sqlite_schema",
  "path": "app.db/grants",
  "table": "grants",
  "generation": "[..]",
  "objects": [
    {
      "type": "table",
      "name": "grants",
      "table": "grants",
      "sql": "CREATE TABLE grants (\n  id INTEGER PRIMARY KEY,\n  owner INTEGER,\n  tag TEXT,\n  FOREIGN KEY (owner, tag) REFERENCES tags(owner, tag)\n)",
      "segment": "grants"
    }
  ],
  "foreign_keys": [
    {
      "table": "grants",
      "fields": [
        "owner",
        "tag"
      ],
      "references": "tags",
      "to": [
        "owner",
        "tag"
      ]
    }
  ]
}
? 0
```

```console
$ metab dbroot --api '/api/plugin/sqlite/schema?path=app.db/nothing'
api: /api/plugin/sqlite/schema?path=app.db/nothing
status: 404
{
  "type": "sqlite_error",
  "path": "app.db/nothing",
  "code": "table_not_found",
  "error": "no table 'nothing' in this database"
}
Error: /api/plugin/sqlite/schema?path=app.db/nothing returned HTTP 404
? 1
```

## Test: the Info view at a table’s address

Every route of the plugin takes a table’s address and answers for its database.

```console
$ metab dbroot --api '/api/plugin/sqlite/info?path=app.db/users' > info.txt
? 0
```

```console
$ grep -E -A3 '"access"' info.txt
  "access": {
    "mode": "immutable",
    "state": "current",
    "reason": "a rollback-journal database is read without a lock, validated against a commit",
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
