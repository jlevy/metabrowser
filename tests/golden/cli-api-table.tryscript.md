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
  mkdir -p tableroot &&
  printf 'name,age,score,joined,active,note\nAda,36,1.5,2020-01-02,true,first\nBob,,2.25,2021-03-04,false,\nCy,unknown,1e999,2019-12-31,true,"quoted, with a comma"\nDee,99999999999999999999,0.5,2022-07-08,false\nEve,41,3,2018-05-06,true,x,y,z\n' > tableroot/people.csv &&
  printf 'city\tpop\nOslo\t709000\nLima\t10000000\n' > tableroot/cities.tsv &&
  printf 'plain text\n' > tableroot/notes.txt &&
  touch -t 202311142213.20 tableroot/people.csv tableroot/cities.tsv tableroot/notes.txt
---
# Golden tests: the table routes over delimited text

The built-in `table` plugin serves every tabular source through five routes under
`/api/plugin/table/`, and the kind of the file at `?path=` picks the source’s adapter.
These transcripts run them over the `delimited` source, `.csv` and `.tsv` files, which
are each one table whose rows are named by their position in the file.

A generation is the file’s identity, size, and modification time, so it differs from one
checkout to the next and the transcripts elide it.

## Test: a delimited file is its own single table

```console
$ metab tableroot --show people.csv
show: people.csv
route: /view/people.csv
kind: delimited
views: source (default)
model: text envelope; size=228 content_bytes=228 content_truncated=False
? 0
```

```console
$ metab tableroot --api '/api/plugin/table/tables?path=people.csv'
api: /api/plugin/table/tables?path=people.csv
status: 200
{
  "type": "table_list",
  "path": "people.csv",
  "generation": "[..]",
  "tables": [
    {
      "id": "",
      "label": "people.csv",
      "group": "tables",
      "keyed": false,
      "estimate": null,
      "path": "people.csv"
    }
  ]
}
? 0
```

## Test: the schema infers each column’s type from its values

`age` holds `unknown` among its first rows, so it is text; `score` and `active` are
typed.
Rows longer than the header add one `extra` field, a list, which neither sorts nor
filters. No field is a key, so rows are named by position.

```console
$ metab tableroot --api '/api/plugin/table/schema?path=people.csv' | grep -E '^      "(name|type|numeric|list|sortable|filterable)":|^  "key":'
  "key": [],
      "name": "name",
      "type": "text",
      "list": false,
      "sortable": true,
      "filterable": true,
      "numeric": false
      "name": "age",
      "type": "text",
      "list": false,
      "sortable": true,
      "filterable": true,
      "numeric": false
      "name": "score",
      "type": "real",
      "list": false,
      "sortable": true,
      "filterable": true,
      "numeric": true
      "name": "joined",
      "type": "date",
      "list": false,
      "sortable": true,
      "filterable": true,
      "numeric": false
      "name": "active",
      "type": "boolean",
      "list": false,
      "sortable": true,
      "filterable": true,
      "numeric": false
      "name": "note",
      "type": "text",
      "list": false,
      "sortable": true,
      "filterable": true,
      "numeric": false
      "name": "extra",
      "type": "text",
      "list": true,
      "sortable": false,
      "filterable": false,
      "numeric": false
? 0
```

## Test: one descriptor shape for every field

A source fills in what it knows and leaves the rest null; a delimited file declares no
types, keys, or references, so those are null or empty.

```console
$ metab tableroot --api '/api/plugin/table/schema?path=cities.tsv'
api: /api/plugin/table/schema?path=cities.tsv
status: 200
{
  "type": "table_schema",
  "path": "cities.tsv",
  "table": "",
  "generation": "[..]",
  "key": [],
  "default_columns": [
    "city",
    "pop"
  ],
  "fields": [
    {
      "name": "city",
      "title": null,
      "type": "text",
      "declared_type": null,
      "nullable": null,
      "key": false,
      "hidden": null,
      "generated": null,
      "list": false,
      "enum": null,
      "format": null,
      "ref": null,
      "sortable": true,
      "sort_note": null,
      "filterable": true,
      "numeric": false
    },
    {
      "name": "pop",
      "title": null,
      "type": "integer",
      "declared_type": null,
      "nullable": null,
      "key": false,
      "hidden": null,
      "generated": null,
      "list": false,
      "enum": null,
      "format": null,
      "ref": null,
      "sortable": true,
      "sort_note": null,
      "filterable": true,
      "numeric": true
    }
  ],
  "references": [],
  "referenced_by": []
}
? 0
```

## Test: a page in the collection envelope

Each cell keeps what a plain JSON value would lose: an infinite real is `{real}`, a
short row’s missing cells are absent (Dee has no `note`), and a long row’s extra cells
are a list. The next page continues from `next_after`, a cursor naming a position.

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&cols=name,score,note,extra&limit=4'
api: /api/plugin/table/rows?path=people.csv&cols=name,score,note,extra&limit=4
status: 200
{
  "type": "table_rows",
  "path": "people.csv",
  "table": "",
  "generation": "[..]",
  "columns": [
    "name",
    "score",
    "note",
    "extra"
  ],
  "rows": [
    {
      "key": "@1",
      "cells": {
        "name": "Ada",
        "score": 1.5,
        "note": "first"
      }
    },
    {
      "key": "@2",
      "cells": {
        "name": "Bob",
        "score": 2.25,
        "note": ""
      }
    },
    {
      "key": "@3",
      "cells": {
        "name": "Cy",
        "score": {
          "real": "inf"
        },
        "note": "quoted, with a comma"
      }
    },
    {
      "key": "@4",
      "cells": {
        "name": "Dee",
        "score": 0.5
      }
    }
  ],
  "next_after": "c.WzRd",
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 5,
  "count_complete": true,
  "estimate": null,
  "skipped": 0,
  "examined": null,
  "searched": null
}
? 0
```

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&cols=name,extra&after=c.WzRd' | grep -A12 '"rows"'
  "rows": [
    {
      "key": "@5",
      "cells": {
        "name": "Eve",
        "extra": [
          "y",
          "z"
        ]
      }
    }
  ],
  "next_after": null,
? 0
```

## Test: sort in both directions, filter, and search

A sort puts a typed column’s nulls first ascending and last descending, with the row’s
position breaking ties in the same direction.
A filter compares typed values (`f.<field>=<op>:<value>`), and a search reads text
fields only and names them.

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&sort=score&cols=name,score' | grep -E '"(key|name|score)":'
      "key": "@4",
        "name": "Dee",
        "score": 0.5
      "key": "@1",
        "name": "Ada",
        "score": 1.5
      "key": "@2",
        "name": "Bob",
        "score": 2.25
      "key": "@5",
        "name": "Eve",
        "score": 3.0
      "key": "@3",
        "name": "Cy",
        "score": {
? 0
```

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&sort=score&order=desc&cols=name&limit=2' | grep -E '"(key|next_after)"'
      "key": "@3",
      "key": "@5",
  "next_after": "c.WzEsMy4wLDVd",
? 0
```

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&f.active=eq:true&f.score=lt:3&cols=name' | grep -E '"(key|count)"'
      "key": "@1",
  "count": 1,
? 0
```

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&q=COMMA&cols=name' | grep -E '"key"|"searched"' -A3
      "key": "@3",
      "cells": {
        "name": "Cy"
      }
--
  "searched": [
    "name",
    "age",
    "note"
? 0
```

## Test: one record, and a hover card

A record named by position says so, and with the generation it was read under, whether
the content has changed since, so the row there may be another.

```console
$ metab tableroot --api '/api/plugin/table/record?path=people.csv&key=@4&generation=stale'
api: /api/plugin/table/record?path=people.csv&key=@4&generation=stale
status: 200
{
  "type": "table_record",
  "path": "people.csv",
  "table": "",
  "key": "@4",
  "positional": true,
  "generation": "[..]",
  "generation_moved": true,
  "cells": {
    "name": "Dee",
    "age": "99999999999999999999",
    "score": 0.5,
    "joined": "2022-07-08",
    "active": false
  },
  "referenced_by": []
}
? 0
```

```console
$ metab tableroot --api '/api/plugin/table/card?path=cities.tsv&key=@2'
api: /api/plugin/table/card?path=cities.tsv&key=@2
status: 200
{
  "type": "table_card",
  "path": "cities.tsv",
  "table": "",
  "key": "@2",
  "generation": "[..]",
  "label": "Lima",
  "cells": {
    "pop": 10000000
  }
}
? 0
```

## Test: refusals name their cause

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&sort=extra'
api: /api/plugin/table/rows?path=people.csv&sort=extra
status: 400
{
  "type": "table_error",
  "path": "people.csv",
  "code": "bad_query",
  "error": "field 'extra' is not sortable: the cells of rows longer than the header, as a list",
  "param": "sort",
  "field": "extra"
}
Error: /api/plugin/table/rows?path=people.csv&sort=extra returned HTTP 400
? 1
```

```console
$ metab tableroot --api '/api/plugin/table/rows?path=people.csv&f.score=gt:high'
api: /api/plugin/table/rows?path=people.csv&f.score=gt:high
status: 400
{
  "type": "table_error",
  "path": "people.csv",
  "code": "bad_query",
  "error": "'high' is not a number",
  "param": "f.score"
}
Error: /api/plugin/table/rows?path=people.csv&f.score=gt:high returned HTTP 400
? 1
```

```console
$ metab tableroot --api '/api/plugin/table/record?path=people.csv&key=@9'
api: /api/plugin/table/record?path=people.csv&key=@9
status: 404
{
  "type": "table_error",
  "path": "people.csv",
  "code": "record_not_found",
  "error": "'@9' names no row of this file",
  "key": "@9"
}
Error: /api/plugin/table/record?path=people.csv&key=@9 returned HTTP 404
? 1
```

```console
$ metab tableroot --api '/api/plugin/table/schema?path=notes.txt'
api: /api/plugin/table/schema?path=notes.txt
status: 404
{
  "type": "table_error",
  "path": "notes.txt",
  "code": "not_a_table_source",
  "error": "files of kind 'text' are not tables",
  "kind": "text"
}
Error: /api/plugin/table/schema?path=notes.txt returned HTTP 404
? 1
```
