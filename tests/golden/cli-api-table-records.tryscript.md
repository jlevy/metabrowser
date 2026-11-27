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
  mkdir -p listroot &&
  printf '[\n  {"name": "Ada", "age": 36, "joined": "2020-01-02", "tags": ["math", "engines"], "meta": {"born": 1815}},\n  {"name": "Bob", "age": "unknown", "joined": "2021-03-04", "tags": [], "active": true},\n  {"name": "Cy", "age": 41.5, "joined": "2019-12-31", "meta": null},\n  {"name": "Dee", "age": 99999999999999999999, "joined": "2022-07-08", "active": false}\n]\n' > listroot/people.json &&
  printf -- '- city: Oslo\n  founded: 1040-01-01\n  pop: 709000\n- city: Lima\n  founded: 1535-01-18\n  pop: 10000000\n' > listroot/cities.yaml &&
  printf '{"name": "metabrowser", "version": 1}\n' > listroot/package.json &&
  printf '[{"a": 1}, "two"]\n' > listroot/mixed.json &&
  printf '[{"a": ' > listroot/broken.json &&
  touch -t 202311142213.20 listroot/people.json listroot/cities.yaml listroot/package.json listroot/mixed.json listroot/broken.json
---
# Golden tests: the table routes over record lists

A JSON or YAML file opens in Table with Tree and Source beside it.
Table renders individual mappings as fields and values.
Record lists use the shared grid, whose table routes serve each mapping as a row named
by its position.
The fields are the mappings’ keys in the order each first appears, typed
from their values. The record-list routes return `source_unreadable` for other shapes or
malformed documents.

A generation is the file’s identity, size, and modification time, so it differs from one
checkout to the next and the transcripts elide it.

## Test: a record list opens in Table

```console
$ metab listroot --show people.json
show: people.json
route: /view/people.json
kind: structured
views: table (default, key A), tree (key V), source (key S)
model: text envelope; size=[..] content_bytes=[..] content_truncated=False
? 0
```

```console
$ metab listroot --show cities.yaml
show: cities.yaml
route: /view/cities.yaml
kind: structured
views: table (default, key A), tree (key V), source (key S)
model: text envelope; size=[..] content_bytes=[..] content_truncated=False
? 0
```

## Test: a mapping also opens in Table

```console
$ metab listroot --show package.json
show: package.json
route: /view/package.json
kind: structured
views: table (default, key A), tree (key V), source (key S)
model: text envelope; size=[..] content_bytes=[..] content_truncated=False
? 0
```

## Test: Table is offered before the document is parsed

```console
$ metab listroot --show mixed.json
show: mixed.json
route: /view/mixed.json
kind: structured
views: table (default, key A), tree (key V), source (key S)
model: text envelope; size=[..] content_bytes=[..] content_truncated=False
? 0
```

```console
$ metab listroot --show broken.json
show: broken.json
route: /view/broken.json
kind: structured
views: table (default, key A), tree (key V), source (key S)
model: text envelope; size=[..] content_bytes=[..] content_truncated=False
? 0
```

```console
$ metab listroot --api '/api/plugin/table/tables?path=people.json'
api: /api/plugin/table/tables?path=people.json
status: 200
{
  "type": "table_list",
  "path": "people.json",
  "generation": "[..]",
  "tables": [
    {
      "id": "",
      "label": "people.json",
      "group": "tables",
      "keyed": false,
      "estimate": null,
      "path": "people.json"
    }
  ]
}
? 0
```

## Test: fields are the keys, typed from their values

`age` holds numbers and text, so its type is `unknown` and each value is shown as its
own type; `joined` is text whose values are all dates; `tags` and `meta` hold nested
values, `json`, which have no order to sort by; and `active`, which two records lack, is
a boolean.

```console
$ metab listroot --api '/api/plugin/table/schema?path=people.json'
api: /api/plugin/table/schema?path=people.json
status: 200
{
  "type": "table_schema",
  "path": "people.json",
  "table": "",
  "generation": "[..]",
  "key": [],
  "default_columns": [
    "name",
    "age",
    "joined",
    "tags",
    "meta",
    "active"
  ],
  "fields": [
    {
      "name": "name",
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
      "name": "age",
      "title": null,
      "type": "unknown",
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
      "sort_note": "values of several types: nulls first, then numbers, then text, then nested values; a filter value that reads as a number matches numbers only",
      "filterable": true,
      "numeric": false
    },
    {
      "name": "joined",
      "title": null,
      "type": "date",
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
      "sort_note": "sorted as text: a value's date and time as written, not its instant, so values that mix separators or offsets sort by their spelling",
      "filterable": true,
      "numeric": false
    },
    {
      "name": "tags",
      "title": null,
      "type": "json",
      "declared_type": null,
      "nullable": null,
      "key": false,
      "hidden": null,
      "generated": null,
      "list": false,
      "enum": null,
      "format": null,
      "ref": null,
      "sortable": false,
      "sort_note": "a nested mapping or list has no order",
      "filterable": true,
      "numeric": false
    },
    {
      "name": "meta",
      "title": null,
      "type": "json",
      "declared_type": null,
      "nullable": null,
      "key": false,
      "hidden": null,
      "generated": null,
      "list": false,
      "enum": null,
      "format": null,
      "ref": null,
      "sortable": false,
      "sort_note": "a nested mapping or list has no order",
      "filterable": true,
      "numeric": false
    },
    {
      "name": "active",
      "title": null,
      "type": "boolean",
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
    }
  ],
  "references": [],
  "referenced_by": []
}
? 0
```

## Test: a page: absent values, nested values, and a number past a browser’s

A key a mapping lacks is absent from its row’s cells, apart from `null`. A nested value
is `{json}`, the value itself, and an integer past what a browser number holds keeps its
digits.

```console
$ metab listroot --api '/api/plugin/table/rows?path=people.json'
api: /api/plugin/table/rows?path=people.json
status: 200
{
  "type": "table_rows",
  "path": "people.json",
  "table": "",
  "generation": "[..]",
  "columns": [
    "name",
    "age",
    "joined",
    "tags",
    "meta",
    "active"
  ],
  "rows": [
    {
      "key": "@1",
      "cells": {
        "name": "Ada",
        "age": 36,
        "joined": "2020-01-02",
        "tags": {
          "json": [
            "math",
            "engines"
          ]
        },
        "meta": {
          "json": {
            "born": 1815
          }
        }
      }
    },
    {
      "key": "@2",
      "cells": {
        "name": "Bob",
        "age": "unknown",
        "joined": "2021-03-04",
        "tags": {
          "json": []
        },
        "active": true
      }
    },
    {
      "key": "@3",
      "cells": {
        "name": "Cy",
        "age": 41.5,
        "joined": "2019-12-31",
        "meta": null
      }
    },
    {
      "key": "@4",
      "cells": {
        "name": "Dee",
        "age": {
          "int": "99999999999999999999"
        },
        "joined": "2022-07-08",
        "active": false
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 4,
  "count_complete": true,
  "estimate": null,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

## Test: a field of several types sorts numbers before text

```console
$ metab listroot --api '/api/plugin/table/rows?path=people.json&sort=age&order=desc&cols=name&cols=age'
api: /api/plugin/table/rows?path=people.json&sort=age&order=desc&cols=name&cols=age
status: 200
{
  "type": "table_rows",
  "path": "people.json",
  "table": "",
  "generation": "[..]",
  "columns": [
    "name",
    "age"
  ],
  "rows": [
    {
      "key": "@2",
      "cells": {
        "name": "Bob",
        "age": "unknown"
      }
    },
    {
      "key": "@4",
      "cells": {
        "name": "Dee",
        "age": {
          "int": "99999999999999999999"
        }
      }
    },
    {
      "key": "@3",
      "cells": {
        "name": "Cy",
        "age": 41.5
      }
    },
    {
      "key": "@1",
      "cells": {
        "name": "Ada",
        "age": 36
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 4,
  "count_complete": true,
  "estimate": null,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

## Test: a filter on a field of several types compares a number as a number

```console
$ metab listroot --api '/api/plugin/table/rows?path=people.json&f.age=gt:40&cols=name&cols=age'
api: /api/plugin/table/rows?path=people.json&f.age=gt:40&cols=name&cols=age
status: 200
{
  "type": "table_rows",
  "path": "people.json",
  "table": "",
  "generation": "[..]",
  "columns": [
    "name",
    "age"
  ],
  "rows": [
    {
      "key": "@2",
      "cells": {
        "name": "Bob",
        "age": "unknown"
      }
    },
    {
      "key": "@3",
      "cells": {
        "name": "Cy",
        "age": 41.5
      }
    },
    {
      "key": "@4",
      "cells": {
        "name": "Dee",
        "age": {
          "int": "99999999999999999999"
        }
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 3,
  "count_complete": true,
  "estimate": null,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

## Test: a search reads the text fields and says which

```console
$ metab listroot --api '/api/plugin/table/rows?path=people.json&q=b&cols=name'
api: /api/plugin/table/rows?path=people.json&q=b&cols=name
status: 200
{
  "type": "table_rows",
  "path": "people.json",
  "table": "",
  "generation": "[..]",
  "columns": [
    "name"
  ],
  "rows": [
    {
      "key": "@2",
      "cells": {
        "name": "Bob"
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 1,
  "count_complete": true,
  "estimate": null,
  "skipped": 0,
  "examined": null,
  "searched": [
    "name"
  ],
  "sort_refused": null,
  "limit": 100
}
? 0
```

## Test: a record carries each nested value whole, and a card a few fields

```console
$ metab listroot --api '/api/plugin/table/record?path=people.json&key=@1'
api: /api/plugin/table/record?path=people.json&key=@1
status: 200
{
  "type": "table_record",
  "path": "people.json",
  "table": "",
  "key": "@1",
  "positional": true,
  "generation": "[..]",
  "generation_moved": null,
  "cells": {
    "name": "Ada",
    "age": 36,
    "joined": "2020-01-02",
    "tags": {
      "json": [
        "math",
        "engines"
      ]
    },
    "meta": {
      "json": {
        "born": 1815
      }
    }
  },
  "referenced_by": []
}
? 0
```

```console
$ metab listroot --api '/api/plugin/table/card?path=people.json&key=@2'
api: /api/plugin/table/card?path=people.json&key=@2
status: 200
{
  "type": "table_card",
  "path": "people.json",
  "table": "",
  "key": "@2",
  "generation": "[..]",
  "label": "Bob",
  "cells": {
    "age": "unknown",
    "joined": "2021-03-04",
    "tags": {
      "json": []
    },
    "active": true
  }
}
? 0
```

## Test: a YAML list, whose dates the parse reads as dates

```console
$ metab listroot --api '/api/plugin/table/rows?path=cities.yaml&sort=pop&order=desc'
api: /api/plugin/table/rows?path=cities.yaml&sort=pop&order=desc
status: 200
{
  "type": "table_rows",
  "path": "cities.yaml",
  "table": "",
  "generation": "[..]",
  "columns": [
    "city",
    "founded",
    "pop"
  ],
  "rows": [
    {
      "key": "@2",
      "cells": {
        "city": "Lima",
        "founded": "1535-01-18",
        "pop": 10000000
      }
    },
    {
      "key": "@1",
      "cells": {
        "city": "Oslo",
        "founded": "1040-01-01",
        "pop": 709000
      }
    }
  ],
  "next_after": null,
  "complete": true,
  "truncated": false,
  "reason": null,
  "count": 2,
  "count_complete": true,
  "estimate": null,
  "skipped": 0,
  "examined": null,
  "searched": null,
  "sort_refused": null,
  "limit": 100
}
? 0
```

## Test: a document that is not a list of records is refused, saying why

```console
$ metab listroot --api '/api/plugin/table/schema?path=package.json'
api: /api/plugin/table/schema?path=package.json
status: 422
{
  "type": "table_error",
  "path": "package.json",
  "code": "source_unreadable",
  "error": "This document is not a list of records: its top level is a mapping, not a list."
}
Error: /api/plugin/table/schema?path=package.json returned HTTP 422
? 1
```

```console
$ metab listroot --api '/api/plugin/table/rows?path=mixed.json'
api: /api/plugin/table/rows?path=mixed.json
status: 422
{
  "type": "table_error",
  "path": "mixed.json",
  "code": "source_unreadable",
  "error": "This document is not a list of records: item 2 of its list is text, not a mapping."
}
Error: /api/plugin/table/rows?path=mixed.json returned HTTP 422
? 1
```

```console
$ metab listroot --api '/api/plugin/table/schema?path=broken.json'
api: /api/plugin/table/schema?path=broken.json
status: 422
{
  "type": "table_error",
  "path": "broken.json",
  "code": "source_unreadable",
  "error": "This file could not be parsed.",
  "detail": "ValueError: <string>:1 Unexpected end of input at column 8"
}
Error: /api/plugin/table/schema?path=broken.json returned HTTP 422
? 1
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
