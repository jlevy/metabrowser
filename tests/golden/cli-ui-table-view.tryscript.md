---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the table view

## Test: a collection publishes a stable catalog

```console
$ node tests/dom/softschema-collection-session.js
{
  "cold index": "Indexing collection…",
  "collection discovery": "Indexing collection… 512 paths checked",
  "partial index": "Some records may be missing because the scan reached its total size limit and 2 paths could not be read.",
  "bounded scan": "Some records may be missing because the scan reached its file and folder limit and 1 file was too large to read.",
  "published table": {
    "label": "Person",
    "count": "577 records",
    "href": "/view/people?table=person%2Fv2"
  },
  "background refresh": "the catalog stays visible without its indexing spinner",
  "return before the renderer arrives": "the catalog keeps the same links",
  "return from a mounted table": "/view/people?table="
}
? 0
```

## Test: open a keyed row, its source file, and its table catalog

```console
$ node tests/dom/table-view-session.js record-links
{
  "return to the folder's table catalog": {
    "href": "/view/archive/people?table="
  },
  "open the linked name of a keyed row": {
    "name": "Ada Lovelace",
    "href": "/view/archive/people?record=r.ada&table=people&context=__record__",
    "title": "Ada Lovelace"
  },
  "open the record's source file": {
    "path": "archive/people/ada.json",
    "href": "/view/archive/people/ada.json",
    "opened": "archive/people/ada.json"
  }
}
? 0
```

## Test: a direct relationship filter resolves its record after the schema

```console
$ node tests/dom/table-view-session.js relationships
{
  "during schema loading": {
    "requests": [
      "schema?path=market.db%2Forders"
    ],
    "hasRelatedLink": false
  },
  "after the schema resolves": {
    "requests": [
      "card?key=k.WzFd&path=market.db%2Fpeople",
      "rows?limit=200&path=market.db%2Forders&ref=people%3Ak.WzFd&via=%5B%5B%22buyer%22%5D%2C%5B%22id%22%5D%5D"
    ],
    "label": "Referencing Ada Lovelace via Buyer",
    "target": "market.db/people",
    "description": "The person who bought it."
  },
  "removing the chip clears the scope": {
    "requests": [
      "rows?limit=200&path=market.db%2Forders"
    ],
    "query": ""
  }
}
? 0
```

The table plugin draws one table of a tabular source.
The server sorts, filters, searches, pages, and counts, and each of those is a route
that `metab --api` reads (`cli-api-table.tryscript.md`); this session pins what the page
does with the answers.
It loads the plugin’s production modules, `table-model.js` and `table-view.js`, and
drives `mountTable` through a scripted page whose answers are the server’s, recorded in
`tests/fixtures/table-view-responses.json`,
`tests/fixtures/table-view-long-responses.json`,
`tests/fixtures/table-view-bounds-responses.json`, and
`tests/fixtures/table-view-records-responses.json` by `tests/test_table_view_session.py`
over the files in `tests/fixtures/table-view/` and the small files that recorder writes,
each with the bound it shows lowered to meet it.

The address holds the view’s state: a header’s press sorts ascending, then descending,
then back to the table’s own order; a boolean value’s press adds a filter, which a chip
removes; Search asks once the typing pauses and replaces the address rather than adding
to its history; a header’s menu, a dialog, filters its column and hides it, replacing
the address as the Columns menu does; and Back shows the address before.
The grid is one Tab stop: `j` and `k` move a row, Right and Left move between the row
and its cells, `k` from the first row reaches the header, whose buttons Right crosses,
and Enter opens the row’s record in place of the grid, whose Back returns the keyboard
to the row; Escape in a record returns to the table.
A run of key presses writes the view’s place to the history entry once, a pause after
the last, so Enter still pushes the record’s address and its Back link goes Back to the
place the keys left; when the browser dropped that push, the Back link replaces the
address with the table’s instead of leaving the table.
A new answer to the same question (`refresh()`) keeps the focused row, the scroll, and
the selection by key.
A refusal is said in an alert with a way back to the whole table, and a view disposed
before its answers arrive draws nothing from them.

A table past the whole-table bound is a grid that draws only a window of its rows over
two spacers, reads the next page as the window nears the last row held, selects rows
that copy as tab-separated values, and draws every row held to print.
A key held with Command, Control, or Option is the browser’s.

The answers a bound shapes are drawn as what they are.
A page of wide rows carries fewer rows than the view asked for, and the view reads on
from each `next_after` rather than counting on its own page size; `cols` names one field
a parameter, so a name with a comma is one column.
A search the time budget stopped shows the matches among the rows it read, says so, and
its cursor continues among them; a sort the budget refused has no rows, and the view
names the field and offers the table’s own order, or to try again, instead of saying the
table is empty. A file read in part says whether every row or only the leading rows were
read. A cursor names the sort and order it was made for, so a new sort is a new question
read from its first page.

The structured kind’s Table view draws a JSON list of mappings through the same view.
A nested value is its JSON text in the grid, and in the record it is drawn by the
renderer the source’s view hands the table, the structured plugin’s inline tree, which a
stand-in takes the place of here; going back to the table releases each tree.
A field whose values are of several types sorts numbers before text.
The server offers the Table tab only on a file that starts as a list of records, so a
mapping has none; a list one of whose items is not a mapping still has the tab, and it
says the file is not a list of records in place of the table, with no toolbar and no way
back to a table it does not have.

```console
$ node tests/dom/table-view-session.js
{
  "the model: an address round trip, cells a delimited file cannot hold, and column fit": {
    "address in": "sort=score&order=desc&f.active=eq%3Atrue&q=x&cols=name&cols=a%2C+b&plain=1&record=%404",
    "address out": "sort=score&order=desc&q=x&f.active=eq%3Atrue&cols=name&cols=a%2C+b&record=%404&plain=1",
    "a column whose name holds a comma": [
      "name",
      "a, b"
    ],
    "reference": {
      "kind": "ref",
      "text": "Ada",
      "ref": {
        "table": "users",
        "key": "k.WzFd",
        "label": "Ada"
      }
    },
    "stored type": {
      "text": "x",
      "stored": "text",
      "tip": "x\nStored as text, not integer"
    },
    "default columns in 210 px": {
      "visible": [
        "a",
        "b"
      ],
      "hidden": [
        "c"
      ],
      "pinned": false
    },
    "chosen columns in 210 px": {
      "visible": [
        "a",
        "b",
        "c"
      ],
      "hidden": [],
      "pinned": true
    },
    "a later page: the question's end, and a changed table's": {
      "joined": {
        "rows": 2,
        "complete": false,
        "reason": "budget"
      },
      "expired": {
        "rows": 1,
        "complete": false,
        "reason": "cursor_expired"
      }
    },
    "no rows match, said of a scan the budget stopped": [
      "No rows match.",
      "No matches among the first 4,096 rows."
    ],
    "window at 1,000 px of 31 px rows": {
      "start": 20,
      "end": 55
    }
  },
  "a small table, read and drawn whole": {
    "requests": [
      "schema?path=people.csv",
      "rows?limit=200&path=people.csv"
    ],
    "address": "",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | 1.5 [num] | 2020-01-02 [mono] | true | first | — [absent]",
        "2 | Bob |  [empty] | 2.25 [num] | 2021-03-04 [mono] | false |  [empty] | — [absent]",
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]",
        "4 | Dee | 99999999999999999999 | 0.5 [num] | 2022-07-08 [mono] | false | — [absent] | — [absent]",
        "5 | Eve | 41 | 3 [num] | 2018-05-06 [mono] | true | x | y, z"
      ]
    },
    "record": null,
    "focus": null
  },
  "its score header, pressed: ascending": {
    "requests": [
      "rows?limit=200&order=asc&path=people.csv&sort=score"
    ],
    "address": "sort=score",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score ↑ (ascending)",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": [
        "4 | Dee | 99999999999999999999 | 0.5 [num] | 2022-07-08 [mono] | false | — [absent] | — [absent]",
        "1 | Ada | 36 | 1.5 [num] | 2020-01-02 [mono] | true | first | — [absent]",
        "2 | Bob |  [empty] | 2.25 [num] | 2021-03-04 [mono] | false |  [empty] | — [absent]",
        "5 | Eve | 41 | 3 [num] | 2018-05-06 [mono] | true | x | y, z",
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]"
      ]
    },
    "record": null,
    "focus": null
  },
  "pressed again: descending": {
    "requests": [
      "rows?limit=200&order=desc&path=people.csv&sort=score"
    ],
    "address": "sort=score&order=desc",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score ↓ (descending)",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": [
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]",
        "5 | Eve | 41 | 3 [num] | 2018-05-06 [mono] | true | x | y, z",
        "2 | Bob |  [empty] | 2.25 [num] | 2021-03-04 [mono] | false |  [empty] | — [absent]",
        "1 | Ada | 36 | 1.5 [num] | 2020-01-02 [mono] | true | first | — [absent]",
        "4 | Dee | 99999999999999999999 | 0.5 [num] | 2022-07-08 [mono] | false | — [absent] | — [absent]"
      ]
    },
    "record": null,
    "focus": null
  },
  "and again: the file's order, which asks again": {
    "requests": [
      "rows?limit=200&path=people.csv"
    ],
    "address": "",
    "header": [
      "#",
      "name",
      "age",
      "score",
      "joined",
      "active",
      "note",
      "extra"
    ]
  },
  "a boolean value, pressed: a filter": {
    "requests": [
      "rows?f.active=eq%3Atrue&limit=200&path=people.csv"
    ],
    "address": "f.active=eq%3Atrue",
    "status": "3 rows match",
    "chips": [
      "active is true"
    ],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 3,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | 1.5 [num] | 2020-01-02 [mono] | true | first | — [absent]",
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]",
        "5 | Eve | 41 | 3 [num] | 2018-05-06 [mono] | true | x | y, z"
      ]
    },
    "record": null,
    "focus": null
  },
  "its chip's ×: the filter gone": {
    "requests": [
      "rows?limit=200&path=people.csv"
    ],
    "address": "",
    "status": "5 rows",
    "chips": []
  },
  "typed in Search: asked once the typing pauses, the entry replaced": {
    "requests before the pause": [],
    "requests": [
      "rows?limit=200&path=people.csv&q=COMMA"
    ],
    "entries": 6,
    "address": "q=COMMA",
    "status": "1 row matches",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 1,
      "first": "0",
      "spacers": [],
      "rows": [
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]"
      ]
    },
    "record": null,
    "focus": null
  },
  "the keyboard: j, j, k, then Right to a cell and Left back to the row": {
    "after j, j, k": {
      "on": "tr",
      "row": "1",
      "text": "2Bob2.252021-03-04false—",
      "tabStops": 1
    },
    "after Right": {
      "on": "td",
      "row": "1",
      "text": "Bob",
      "tabStops": 1
    },
    "after Left, Left": {
      "on": "tr",
      "row": "1",
      "text": "2Bob2.252021-03-04false—",
      "tabStops": 1
    }
  },
  "Enter on the row: its record, an entry Back returns from": {
    "requests": [
      "record?generation=G&key=%402&path=people.csv"
    ],
    "entries added": 1,
    "address": "record=%402",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | 1.5 [num] | 2020-01-02 [mono] | true | first | — [absent]",
        "2 | Bob |  [empty] | 2.25 [num] | 2021-03-04 [mono] | false |  [empty] | — [absent]",
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]",
        "4 | Dee | 99999999999999999999 | 0.5 [num] | 2022-07-08 [mono] | false | — [absent] | — [absent]",
        "5 | Eve | 41 | 3 [num] | 2018-05-06 [mono] | true | x | y, z"
      ]
    },
    "record": {
      "back": "← Back to the table",
      "title": "Row 2",
      "notes": [
        "This row is named by its position in the table."
      ],
      "fields": [
        "name (text): Bob",
        "age (text): ",
        "score (real): 2.25",
        "joined (date): 2021-03-04",
        "active (boolean): false",
        "note (text): ",
        "extra (text): No value: this row does not have this field."
      ]
    },
    "focus": {
      "on": "a",
      "row": null,
      "text": "← Back to the table",
      "tabStops": 1
    }
  },
  "Back to the table: the grid, the keyboard on the row it opened": {
    "requests": [],
    "address": "",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": []
    },
    "record": null,
    "focus": {
      "on": "tr",
      "row": "1",
      "text": "2Bob2.252021-03-04false—",
      "tabStops": 1
    }
  },
  "the header: k from the first row, Right across its controls, Down to the row": {
    "after k, k": {
      "on": "button",
      "row": null,
      "text": "name",
      "tabStops": 1
    },
    "after Right": {
      "on": "button",
      "row": null,
      "text": "▾",
      "tabStops": 1
    },
    "after Right again": {
      "on": "button",
      "row": null,
      "text": "age",
      "tabStops": 1
    },
    "after Down": {
      "on": "td",
      "row": "0",
      "text": "36",
      "tabStops": 1
    },
    "header controls out of the Tab order": 13
  },
  "a header's menu: closed when the focus leaves it, and by Escape, to its button": {
    "role": "dialog",
    "label": "name: sort, filter, or hide",
    "closed when the focus left": true,
    "open after Escape": false,
    "focus": {
      "on": "button",
      "row": null,
      "text": "▾",
      "tabStops": 1
    }
  },
  "the age header's menu, and a filter from its form": {
    "role": "dialog",
    "menu items": [
      "Sort ascending",
      "Sort descending",
      "Hide column"
    ],
    "operators": [
      "eq",
      "ne",
      "contains",
      "lt",
      "le",
      "gt",
      "ge",
      "null",
      "notnull"
    ],
    "requests": [
      "rows?f.age=contains%3A9&limit=200&path=people.csv"
    ],
    "address": "f.age=contains%3A9",
    "status": "1 row matches",
    "chips": [
      "age contains 9"
    ],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 1,
      "first": "0",
      "spacers": [],
      "rows": [
        "4 | Dee | 99999999999999999999 | 0.5 [num] | 2022-07-08 [mono] | false | — [absent] | — [absent]"
      ]
    },
    "record": null,
    "focus": {
      "on": "button",
      "row": null,
      "text": "▾",
      "tabStops": 1
    }
  },
  "Hide column: the reader's columns, in the address": {
    "requests": [
      "rows?cols=name&cols=age&cols=score&cols=active&cols=note&cols=extra&limit=200&path=people.csv"
    ],
    "address": "cols=name&cols=age&cols=score&cols=active&cols=note&cols=extra",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | 1.5 [num] | true | first | — [absent]",
        "2 | Bob |  [empty] | 2.25 [num] | false |  [empty] | — [absent]"
      ]
    },
    "record": null,
    "focus": {
      "on": "button",
      "row": null,
      "text": "▾",
      "tabStops": 1
    }
  },
  "Columns: each field, checked when shown; Default columns": {
    "listed": [
      "name ✓",
      "age ✓",
      "score ✓",
      "joined",
      "active ✓",
      "note ✓",
      "extra ✓"
    ],
    "requests": [
      "rows?limit=200&path=people.csv"
    ],
    "address": "",
    "header": [
      "#",
      "name",
      "age",
      "score",
      "joined",
      "active",
      "note",
      "extra"
    ]
  },
  "Back: the address before, shown": {
    "requests": [
      "rows?f.age=contains%3A9&limit=200&path=people.csv"
    ],
    "address": "f.age=contains%3A9",
    "header": [
      "#",
      "name",
      "age",
      "score",
      "joined",
      "active",
      "note",
      "extra"
    ]
  },
  "disposed: the window's listeners released": {
    "popstate listeners before": 1,
    "after": 0,
    "beforeprint": 0
  },
  "an address whose filter the route refuses": {
    "requests": [
      "schema?path=people.csv",
      "rows?f.score=gt%3Ahigh&limit=200&path=people.csv"
    ],
    "address": "f.score=gt:high",
    "status": "",
    "chips": [
      "score > high"
    ],
    "notes": [
      "The table could not be read. 'high' is not a number. Show the whole table"
    ],
    "empty": null,
    "table": "hidden",
    "record": null,
    "focus": null
  },
  "a filter no row matches": {
    "requests": [
      "schema?path=people.csv",
      "rows?f.name=eq%3AZed&limit=200&path=people.csv"
    ],
    "address": "f.name=eq:Zed",
    "status": "0 rows match",
    "chips": [
      "name is Zed"
    ],
    "notes": [],
    "empty": "No rows match. Clear the search and filters",
    "table": "hidden",
    "record": null,
    "focus": null
  },
  "an address that names a record: the record, then the rows behind it": {
    "requests": [
      "schema?path=people.csv",
      "record?key=%404&path=people.csv",
      "rows?limit=200&path=people.csv"
    ],
    "address": "record=%404",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "score",
        "joined",
        "active",
        "note",
        "extra"
      ],
      "drawn": 5,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | 1.5 [num] | 2020-01-02 [mono] | true | first | — [absent]",
        "2 | Bob |  [empty] | 2.25 [num] | 2021-03-04 [mono] | false |  [empty] | — [absent]",
        "3 | Cy | unknown | Infinity [num] | 2019-12-31 [mono] | true | quoted, with a comma | — [absent]",
        "4 | Dee | 99999999999999999999 | 0.5 [num] | 2022-07-08 [mono] | false | — [absent] | — [absent]",
        "5 | Eve | 41 | 3 [num] | 2018-05-06 [mono] | true | x | y, z"
      ]
    },
    "record": {
      "back": "← Back to the table",
      "title": "Row 4",
      "notes": [
        "This row is named by its position in the table."
      ],
      "fields": [
        "name (text): Dee",
        "age (text): 99999999999999999999",
        "score (real): 0.5",
        "joined (date): 2022-07-08",
        "active (boolean): false",
        "note (text): No value: this row does not have this field.",
        "extra (text): No value: this row does not have this field."
      ]
    },
    "focus": {
      "on": "a",
      "row": null,
      "text": "← Back to the table",
      "tabStops": 1
    }
  },
  "Escape in the record: the table, the address without the record, replaced": {
    "requests": [],
    "address": "",
    "entries": 1,
    "record": null,
    "drawn": 5
  },
  "disposed before its answers arrived: nothing drawn": {
    "requests": [
      "schema?path=people.csv"
    ],
    "rows": 0,
    "status": ""
  },
  "a table past the whole-table bound: a grid that draws a window": {
    "requests": [
      "schema?path=long.csv",
      "rows?limit=200&path=long.csv"
    ],
    "address": "",
    "status": "600 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": "601",
      "lines": 1,
      "header": [
        "#",
        "n",
        "word",
        "even"
      ],
      "drawn": 25,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 5600px"
      ],
      "rows": [
        "1 | 1 [num] | bravo 1 | false",
        "2 | 2 [num] | charlie 2 | true"
      ]
    },
    "record": null,
    "focus": null
  },
  "scrolled to row 150: the window there, and the next page read ahead": {
    "requests": [
      "rows?after=c.W251bGwsImFzYyIsMjAwXQ&limit=1000&path=long.csv"
    ],
    "address": "",
    "status": "600 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": "601",
      "lines": 1,
      "header": [
        "#",
        "n",
        "word",
        "even"
      ],
      "drawn": 37,
      "first": "140",
      "spacers": [
        "height: 4416px",
        "height: 13600px"
      ],
      "rows": [
        "139 | 139 [num] | bravo 139 | false"
      ]
    },
    "record": null,
    "focus": null
  },
  "End: the last row held, scrolled into the window, focused": {
    "scrollTop": 18837,
    "first": "578",
    "drawn": 24,
    "focus": {
      "on": "tr",
      "row": "599",
      "text": "600600alpha 600true",
      "tabStops": 1
    }
  },
  "Home, then Shift-Down twice: three rows selected, which copy as tab-separated values": {
    "selected": 3,
    "copy handled": true,
    "copied": {
      "type": "text/plain",
      "value": "n\tword\teven\n1\tbravo 1\tfalse\n2\tcharlie 2\ttrue\n3\tdelta 3\tfalse\n"
    }
  },
  "a key held with Command, Control, or Option is the browser's: none moves or is taken": {
    "taken": 0,
    "focus kept": true
  },
  "Home, then Shift-End: every row held selected, the window at the last": {
    "handled": true,
    "drawnSelected": 24,
    "focus": {
      "on": "tr",
      "row": "599",
      "text": "600600alpha 600true",
      "tabStops": 1
    }
  },
  "print draws every row held, and the window again after": {
    "rows while printing": 600,
    "rows after": 24
  },
  "sorted descending: the grid's first rows, its sort said in the header": {
    "requests": [
      "rows?limit=200&order=asc&path=long.csv&sort=n",
      "rows?limit=200&order=desc&path=long.csv&sort=n"
    ],
    "address": "sort=n&order=desc",
    "status": "600 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": "601",
      "lines": 1,
      "header": [
        "#",
        "n ↓ (descending)",
        "word",
        "even"
      ],
      "drawn": 25,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 5600px"
      ],
      "rows": [
        "600 | 600 [num] | alpha 600 | true",
        "599 | 599 [num] | foxtrot 599 | false"
      ]
    },
    "record": null,
    "focus": null
  },
  "150 presses of j: no history write while the keys come, one a pause after": {
    "writes while pressing": 0,
    "writes just before the pause ends": 0,
    "writes after it": 1,
    "requests": [
      "rows?after=c.W251bGwsImFzYyIsMjAwXQ&limit=1000&path=long.csv"
    ],
    "focus": {
      "on": "tr",
      "row": "150",
      "text": "151151bravo 151false",
      "tabStops": 1
    }
  },
  "Enter after them: the record's entry pushed, its address the record's": {
    "entries added": 1,
    "browser's address": "?record=%40151",
    "title": "Row 151",
    "requests": [
      "record?generation=G&key=%40151&path=long.csv"
    ]
  },
  "its Back link: Back, to the grid at the place the keys left": {
    "went back": true,
    "browser's address": "",
    "record": null,
    "scrollTop": 4469,
    "focus": {
      "on": "tr",
      "row": "150",
      "text": "151151bravo 151false",
      "tabStops": 1
    }
  },
  "a push the browser dropped: the record drawn, the browser's address unchanged": {
    "shell's address": "record=%40151",
    "browser's address": "",
    "title": "Row 151",
    "requests": [
      "record?generation=G&key=%40151&path=long.csv"
    ]
  },
  "its Back link: the table's address replaces the entry, and Back is not taken": {
    "went back": false,
    "entries added": 0,
    "browser's address": "",
    "record": null,
    "focus": {
      "on": "tr",
      "row": "150",
      "text": "151151bravo 151false",
      "tabStops": 1
    }
  },
  "refresh: the question asked again, its answer drawn with the place kept by key": {
    "requests": [
      "rows?limit=200&path=long.csv",
      "rows?after=c.W251bGwsImFzYyIsMjAwXQ&limit=1000&path=long.csv"
    ],
    "before": {
      "scrollTop": 4501,
      "focus": {
        "on": "tr",
        "row": "151",
        "text": "152152charlie 152true",
        "tabStops": 1
      },
      "selected": 2
    },
    "after": {
      "scrollTop": 4501,
      "focus": {
        "on": "tr",
        "row": "151",
        "text": "152152charlie 152true",
        "tabStops": 1
      },
      "selected": 2
    }
  },
  "pages shorter than asked: read on from each cursor, the table drawn whole": {
    "requests": [
      "schema?path=paged.csv",
      "rows?limit=200&path=paged.csv",
      "rows?after=c.W251bGwsImFzYyIsM10&limit=1000&path=paged.csv",
      "rows?after=c.W251bGwsImFzYyIsNl0&limit=1000&path=paged.csv"
    ],
    "address": "",
    "status": "8 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "city, state",
        "n"
      ],
      "drawn": 8,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | Austin, TX | 1 [num]",
        "2 | Bob | Boise, ID | 2 [num]",
        "3 | Cy | Chicago, IL | 3 [num]",
        "4 | Dee | Denver, CO | 4 [num]",
        "5 | Eve | Eugene, OR | 5 [num]",
        "6 | Flo | Flint, MI | 6 [num]",
        "7 | Gus | Gary, IN | 7 [num]",
        "8 | Hal | Helena, MT | 8 [num]"
      ]
    },
    "record": null,
    "focus": null
  },
  "a column hidden: the others, one field a parameter, a comma in a name kept": {
    "requests": [
      "rows?cols=name&cols=city%2C+state&limit=200&path=paged.csv",
      "rows?after=c.W251bGwsImFzYyIsNF0&cols=name&cols=city%2C+state&limit=1000&path=paged.csv"
    ],
    "address": "cols=name&cols=city%2C+state",
    "status": "8 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "city, state"
      ],
      "drawn": 8,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | Austin, TX"
      ]
    },
    "record": null,
    "focus": null
  },
  "a search the time budget stopped: the matches it found, said as such": {
    "requests": [
      "schema?path=numbers.csv",
      "rows?limit=200&path=numbers.csv&q=match"
    ],
    "address": "q=match",
    "status": "At least 256 rows match",
    "chips": [],
    "notes": [
      "These are the matches among the first 4,096 rows."
    ],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": "-1",
      "lines": 1,
      "header": [
        "#",
        "n",
        "tag"
      ],
      "drawn": 25,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 5600px"
      ],
      "rows": [
        "1 | 0 [num] | match",
        "17 | 16 [num] | match"
      ]
    },
    "record": null,
    "focus": null
  },
  "scrolled: the next page continues among the rows it read, and ends": {
    "requests": [
      "rows?after=c.W251bGwsImFzYyIsMzE4NV0&limit=1000&path=numbers.csv&q=match"
    ],
    "status": "At least 256 rows match",
    "notes": [
      "These are the matches among the first 4,096 rows."
    ],
    "rowcount": "-1"
  },
  "a sort the time budget refused: said by its field, the file's order offered": {
    "requests": [
      "schema?path=numbers.csv",
      "rows?limit=200&order=asc&path=numbers.csv&sort=n"
    ],
    "address": "sort=n",
    "status": "12,288 rows",
    "chips": [],
    "notes": [
      "This table is too large to sort by “n”. Show the table’s own order."
    ],
    "empty": null,
    "table": "hidden",
    "record": null,
    "focus": null
  },
  "the file's order, chosen: the rows again": {
    "requests": [
      "rows?limit=200&path=numbers.csv"
    ],
    "address": "",
    "status": "12,288 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": "12289",
      "lines": 1,
      "header": [
        "#",
        "n",
        "tag"
      ],
      "drawn": 33,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 5344px"
      ],
      "rows": [
        "1 | 0 [num] | match",
        "2 | 1 [num] | miss"
      ]
    },
    "record": null,
    "focus": null
  },
  "a file whose rows have more cells than the table reads": {
    "requests": [
      "schema?path=cut.csv",
      "rows?limit=200&path=cut.csv"
    ],
    "address": "",
    "status": "2 rows",
    "chips": [],
    "notes": [
      "Some values in this table are too large to show."
    ],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "a",
        "b"
      ],
      "drawn": 2,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | 1 [num] | 2 [num]"
      ]
    },
    "record": null,
    "focus": null
  },
  "a file with more rows than the table reads": {
    "requests": [
      "schema?path=tall.csv",
      "rows?limit=200&path=tall.csv"
    ],
    "address": "",
    "status": "At least 3 rows",
    "chips": [],
    "notes": [
      "Only part of this table is shown, and counts, sorts, and filters cover that part."
    ],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": "-1",
      "lines": 1,
      "header": [
        "#",
        "n"
      ],
      "drawn": 3,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 0px"
      ],
      "rows": [
        "1 | 1 [num]"
      ]
    },
    "record": null,
    "focus": null
  },
  "a JSON list of mappings: a table of its records": {
    "requests": [
      "schema?path=records.json",
      "rows?limit=200&path=records.json"
    ],
    "address": "",
    "status": "3 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age",
        "tags",
        "meta",
        "active"
      ],
      "drawn": 3,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | [\"math\",\"engines\"] [mono] | {\"born\":1815,\"notes\":{\"first\":true}} [mono] | — [absent]",
        "2 | Bob | unknown | [] [mono] | — [mono] [absent] | true",
        "3 | Cy | 41.5 | — [mono] [absent] | null [mono] [null] | — [absent]"
      ]
    },
    "record": null,
    "focus": null
  },
  "a record: each nested value drawn as a tree, an absent field said": {
    "requests": [
      "record?generation=G&key=%401&path=records.json"
    ],
    "record": {
      "back": "← Back to the table",
      "title": "Row 1",
      "notes": [
        "This row is named by its position in the table."
      ],
      "fields": [
        "name (text): Ada",
        "age (unknown): 36",
        "tags (json): tree [\"math\",\"engines\"]",
        "meta (json): tree {\"born\":1815,\"notes\":{\"first\":true}}",
        "active (boolean): No value: this row does not have this field."
      ]
    },
    "trees": 2
  },
  "Back to the table: the trees released": {
    "requests": [],
    "released": 2
  },
  "a field of values of several types, sorted: numbers, then text": {
    "requests": [
      "rows?limit=200&order=asc&path=records.json&sort=age"
    ],
    "address": "sort=age",
    "status": "3 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "grid",
      "rowcount": null,
      "lines": 1,
      "header": [
        "#",
        "name",
        "age ↑ (ascending)",
        "tags",
        "meta",
        "active"
      ],
      "drawn": 3,
      "first": "0",
      "spacers": [],
      "rows": [
        "1 | Ada | 36 | [\"math\",\"engines\"] [mono] | {\"born\":1815,\"notes\":{\"first\":true}} [mono] | — [absent]",
        "3 | Cy | 41.5 | — [mono] [absent] | null [mono] [null] | — [absent]",
        "2 | Bob | unknown | [] [mono] | — [mono] [absent] | true"
      ]
    },
    "record": null,
    "focus": null
  },
  "a JSON list with an item that is not a mapping: said in place of the table": {
    "requests": [
      "schema?path=mixed.json"
    ],
    "toolbar": "hidden",
    "notes": [
      "This document is not a list of records: item 2 of its list is text, not a mapping."
    ],
    "table": "hidden",
    "links": 0
  },
  "requests asked of the server": {
    "unrecorded": []
  }
}
? 0
```

With `live`, the session prints the steps of a table that follows its file
(`tests/fixtures/table-view-live-responses.json` records the answers at each version of
`live.csv`). It watches the file with the generation it read, and a burst of changes is
one read of the rows it holds, with the same question, once the window
`LIVE_COALESCE_MS` ends; the schema is read again only when the rows say a column may
have moved. A refresh after a slow one waits `LIVE_COST_SPACING` times as long as that
one took, and a change while the page is hidden is read once, when it is shown.
A row whose cells changed and a row that arrived flash once; a row that would land above
the reader’s place is offered rather than drawn, said once in the live region, and
taking the offer draws it, goes to it, and puts the keyboard on it; the focus and the
selection stay on their rows, by position where rows have no key, an open menu keeps
what was typed in it and the focus, and a refresh whose rows read the same draws
nothing. A watch refused says the table is not following its file.
A refresh asks the question again as `refresh()` does, from the first page as far as the
reader reached, so a table drawn as a window keeps no rows above the window as last read
(`tests/fixtures/table-view-live-window-responses.json`, sixty rows read in part in
pages of ten). An open record named by position is read again and says when another row
is at its position; read again unchanged it is not drawn again, and the record pane has
its own Live control.
Pausing counts the changes held back and reads once on resuming.
A column the address named that is gone is dropped from it with a notice, and a file
that is gone keeps the rows last read and says so, once however often it is read again;
disposing the view releases the watch.

```console
$ node tests/dom/table-view-session.js live
{
  "live: a table read, its file watched with the generation it read": {
    "requests": [
      "schema?path=live.csv",
      "rows?limit=200&path=live.csv",
      "watch live.csv at G1"
    ],
    "pill": "Live",
    "offer": null,
    "flashing": [],
    "announced": "5 rows",
    "status": "5 rows",
    "notes": [],
    "address": "",
    "rows": [
      "1 | a | 1 [num]",
      "2 | b | 2 [num]",
      "3 | c | 3 [num]",
      "4 | d | 4 [num]",
      "5 | e | 5 [num]"
    ],
    "focus": null
  },
  "live: three changes in a burst, one read again: a cell changed, a row arrived below": {
    "requests before the window ends": [],
    "requests": [
      "rows?limit=200&path=live.csv"
    ],
    "pill": "Live",
    "offer": null,
    "flashing": [
      "2",
      "6"
    ],
    "announced": "5 rows",
    "status": "6 rows",
    "notes": [],
    "address": "",
    "rows": [
      "1 | a | 1 [num]",
      "2 | b | 20 [num]",
      "3 | c | 3 [num]",
      "4 | d | 4 [num]",
      "5 | e | 5 [num]",
      "6 | f | 6 [num]"
    ],
    "focus": {
      "on": "input",
      "row": null,
      "text": "",
      "tabStops": 1
    },
    "menu open, its unsent filter kept": "4"
  },
  "live: the open record, named by position, read again: another row is there now": {
    "requests": [
      "record?key=%402&path=live.csv",
      "rows?limit=200&path=live.csv"
    ],
    "record": {
      "back": "← Back to the table",
      "title": "Row 2",
      "notes": [
        "This row is named by its position in the table."
      ],
      "fields": [
        "name (text): a",
        "qty (integer): 1"
      ]
    },
    "notices": [
      "This table changed since this row was read, so the row at this position may be a different one."
    ]
  },
  "live: back to the table, which was read again behind the record": {
    "requests": [],
    "pill": "Live",
    "offer": null,
    "flashing": [
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7"
    ],
    "announced": "5 rows",
    "status": "7 rows",
    "notes": [],
    "address": "",
    "rows": [
      "1 | z | 9 [num]",
      "2 | a | 1 [num]",
      "3 | b | 20 [num]",
      "4 | c | 3 [num]",
      "5 | d | 4 [num]",
      "6 | e | 5 [num]",
      "7 | f | 6 [num]"
    ],
    "focus": {
      "on": "tr",
      "row": "1",
      "text": "2a1",
      "tabStops": 1
    }
  },
  "live: sorted, scrolled two rows down, a row focused, and paused: changes counted, not read": {
    "scrollTop": 66,
    "requests": [],
    "pill": "Paused · 2 changes",
    "offer": null,
    "flashing": [],
    "announced": "Paused",
    "status": "7 rows",
    "notes": [],
    "address": "sort=qty&order=desc",
    "rows": [
      "3 | b | 20 [num]",
      "1 | z | 9 [num]",
      "7 | f | 6 [num]",
      "6 | e | 5 [num]",
      "5 | d | 4 [num]",
      "4 | c | 3 [num]",
      "2 | a | 1 [num]"
    ],
    "focus": {
      "on": "tr",
      "row": "3",
      "text": "6e5",
      "tabStops": 1
    }
  },
  "live: resumed: the row that sorts above the reader's place offered, the one below drawn, the focus kept": {
    "scrollTop": 66,
    "requests": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ],
    "pill": "Live",
    "offer": "1 new row",
    "flashing": [
      "9"
    ],
    "announced": "1 new row",
    "status": "9 rows",
    "notes": [],
    "address": "sort=qty&order=desc",
    "rows": [
      "3 | b | 20 [num]",
      "1 | z | 9 [num]",
      "7 | f | 6 [num]",
      "6 | e | 5 [num]",
      "5 | d | 4 [num]",
      "4 | c | 3 [num]",
      "2 | a | 1 [num]",
      "9 | h | 0 [num]"
    ],
    "focus": {
      "on": "tr",
      "row": "3",
      "text": "6e5",
      "tabStops": 1
    }
  },
  "live: the offer taken: the new row drawn, the view at it, and the keyboard on it": {
    "scrollTop": 0,
    "requests": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ],
    "pill": "Live",
    "offer": null,
    "flashing": [
      "8"
    ],
    "announced": "1 new row",
    "status": "9 rows",
    "notes": [],
    "address": "sort=qty&order=desc",
    "rows": [
      "8 | g | 100 [num]",
      "3 | b | 20 [num]",
      "1 | z | 9 [num]",
      "7 | f | 6 [num]",
      "6 | e | 5 [num]",
      "5 | d | 4 [num]",
      "4 | c | 3 [num]",
      "2 | a | 1 [num]",
      "9 | h | 0 [num]"
    ],
    "focus": {
      "on": "tr",
      "row": "0",
      "text": "8g100",
      "tabStops": 1
    }
  },
  "live: the file touched, its rows as they were: nothing drawn again, the selection kept": {
    "requests": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ],
    "flashing": [
      "8"
    ],
    "focus": {
      "on": "tr",
      "row": "1",
      "text": "3b20",
      "tabStops": 1
    },
    "selected": [
      "8",
      "3"
    ],
    "first row element kept": true
  },
  "live: a cell changed under the selection, read slowly: the selection stays on its rows": {
    "requests": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ],
    "flashing": [
      "3"
    ],
    "focus": {
      "on": "tr",
      "row": "1",
      "text": "3b21",
      "tabStops": 1
    },
    "selected": [
      "8",
      "3"
    ]
  },
  "live: after a read that took 400 ms, the next waits twice that, not the window": {
    "requests once the window ends": [],
    "requests at twice the last read": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ]
  },
  "live: a change while the page is hidden: nothing read until it is shown, then once": {
    "requests while hidden": [],
    "requests": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ],
    "flashing": [
      "5"
    ]
  },
  "live: a watch refused says the table is not following its file, until it is live again": {
    "notes while refused": [
      "This table is not following changes to its file now."
    ],
    "notes once live": [],
    "pill": "Live"
  },
  "live: a record read again unchanged: not drawn again, the keyboard on its Live control": {
    "requests": [
      "record?key=%403&path=live.csv",
      "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ],
    "record pane drawn again": false,
    "focus": "the record's Live control",
    "record pill": "Live"
  },
  "live: the record's Live control pressed: paused there, a change held back": {
    "requests": [],
    "record pill": "Paused · 1 change"
  },
  "live: the sorted column removed: dropped from the address, with a notice": {
    "requests": [
      "rows?limit=200&order=desc&path=live.csv&sort=qty",
      "schema?path=live.csv",
      "rows?limit=200&path=live.csv"
    ],
    "pill": "Live",
    "offer": null,
    "flashing": [],
    "announced": "9 rows",
    "status": "9 rows",
    "notes": [
      "This table has no “qty” now, so the view no longer uses it."
    ],
    "address": "",
    "rows": [
      "1 | z",
      "2 | a",
      "3 | b",
      "4 | c",
      "5 | d",
      "6 | e",
      "7 | f",
      "8 | g",
      "9 | h"
    ],
    "focus": null
  },
  "live: the file removed: the rows last read kept, and said to be": {
    "requests": [
      "rows?limit=200&path=live.csv",
      "schema?path=live.csv",
      "rows?limit=200&path=live.csv",
      "schema?path=live.csv"
    ],
    "pill": "Live",
    "offer": null,
    "flashing": [],
    "announced": "This file is no longer there, so these are the rows last read.",
    "status": "9 rows",
    "notes": [
      "This table has no “qty” now, so the view no longer uses it.",
      "This file is no longer there, so these are the rows last read."
    ],
    "address": "",
    "rows": [
      "1 | z",
      "2 | a",
      "3 | b",
      "4 | c",
      "5 | d",
      "6 | e",
      "7 | f",
      "8 | g",
      "9 | h"
    ],
    "focus": null,
    "announced, each time": [
      "This file is no longer there, so these are the rows last read."
    ]
  },
  "live: disposed: the watch released": {
    "requests": [
      "unwatch live.csv"
    ]
  },
  "live window: sixty rows read in pages of ten, scrolled to row 40": {
    "requests": 8,
    "first": "30 | 30",
    "rows changed": []
  },
  "live window: rows 5 and 45 changed: read again from the start as far as the reader reached": {
    "requests": [
      "rows?limit=200&path=live-window.csv",
      "rows?after=c.W251bGwsImFzYyIsMTBd&limit=1000&path=live-window.csv",
      "rows?after=c.W251bGwsImFzYyIsMjBd&limit=1000&path=live-window.csv",
      "rows?after=c.W251bGwsImFzYyIsMzBd&limit=1000&path=live-window.csv",
      "rows?after=c.W251bGwsImFzYyIsNDBd&limit=1000&path=live-window.csv",
      "rows?after=c.W251bGwsImFzYyIsNTBd&limit=1000&path=live-window.csv"
    ],
    "first": "30 | 30",
    "rows changed": [
      "45 | 4500"
    ]
  },
  "live window: back at the top: row 5 as read with the rest, nothing stale to read again": {
    "requests as the window arrives": [],
    "rows changed as it arrives": [
      "5 | 500"
    ],
    "requests": [],
    "first": "1 | 1",
    "rows changed": [
      "5 | 500"
    ]
  }
}
? 0
```
