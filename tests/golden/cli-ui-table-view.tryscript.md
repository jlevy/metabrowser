---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the table view

The table plugin draws one table of a tabular source.
The server sorts, filters, searches, pages, and counts, and each of those is a route
that `metab --api` reads (`cli-api-table.tryscript.md`); this session pins what the page
does with the answers.
It loads the plugin’s production modules, `table-model.js` and `table-view.js`, and
drives `mountTable` through a scripted page whose answers are the server’s, recorded in
`tests/fixtures/table-view-responses.json` and
`tests/fixtures/table-view-long-responses.json` by `tests/test_table_view_session.py`
over the files in `tests/fixtures/table-view/`.

The address holds the view’s state: a header’s press sorts ascending, then descending,
then back to the file’s order; a boolean value’s press adds a filter, which a chip
removes; Search asks once the typing pauses and replaces the address rather than adding
to its history; a header’s menu filters and hides its column; and Back shows the address
before.
The grid is one Tab stop: `j` and `k` move a row, Right and Left move between the
row and its cells, and Enter opens the row’s record in place of the grid, whose Back
returns the keyboard to the row; Escape in a record returns to the table.
A refusal is said in an alert with a way back to the whole table, and a view disposed
before its answers arrive draws nothing from them.

A table past the whole-table bound is a grid that draws only a window of its rows over
two spacers, reads the next page as the window nears the last row held, selects rows
that copy as tab-separated values, and draws every row held to print.
A key held with Command, Control, or Option is the browser’s.

```console
$ node tests/dom/table-view-session.js
{
  "the model: an address round trip, cells a delimited file cannot hold, and column fit": {
    "address in": "sort=score&order=desc&f.active=eq%3Atrue&q=x&plain=1&record=%404",
    "address out": "sort=score&order=desc&q=x&f.active=eq%3Atrue&record=%404&plain=1",
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
      "role": "table",
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
      "role": "table",
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
      "role": "table",
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
      "role": "table",
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
      "role": "table",
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
      "role": "table",
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
        "This row is named by its position in the file."
      ],
      "fields": [
        "name (text): Bob",
        "age (text): ",
        "score (real): 2.25",
        "joined (date): 2021-03-04",
        "active (boolean): false",
        "note (text): ",
        "extra (text): No value: this row is shorter than the header."
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
      "role": "table",
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
  "the age header's menu, and a filter from its form": {
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
      "role": "table",
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
    "focus": null
  },
  "Hide column: the reader's columns, in the address": {
    "requests": [
      "rows?cols=name%2Cage%2Cscore%2Cactive%2Cnote%2Cextra&limit=200&path=people.csv"
    ],
    "address": "cols=name%2Cage%2Cscore%2Cactive%2Cnote%2Cextra",
    "status": "5 rows",
    "chips": [],
    "notes": [],
    "empty": null,
    "table": {
      "role": "table",
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
    "focus": null
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
    "requests": [],
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
      "role": "table",
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
        "This row is named by its position in the file."
      ],
      "fields": [
        "name (text): Dee",
        "age (text): 99999999999999999999",
        "score (real): 0.5",
        "joined (date): 2022-07-08",
        "active (boolean): false",
        "note (text): No value: this row is shorter than the header.",
        "extra (text): No value: this row is shorter than the header."
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
      "drawn": 24,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 5808px"
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
      "rows?after=c.WzIwMF0&limit=1000&path=long.csv"
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
      "drawn": 36,
      "first": "140",
      "spacers": [
        "height: 4554px",
        "height: 14058px"
      ],
      "rows": [
        "139 | 139 [num] | bravo 139 | false"
      ]
    },
    "record": null,
    "focus": null
  },
  "End: the last row held, scrolled into the window, focused": {
    "scrollTop": 19437,
    "first": "579",
    "drawn": 23,
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
    "drawnSelected": 23,
    "focus": {
      "on": "tr",
      "row": "599",
      "text": "600600alpha 600true",
      "tabStops": 1
    }
  },
  "print draws every row held, and the window again after": {
    "rows while printing": 600,
    "rows after": 23
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
      "drawn": 24,
      "first": "2",
      "spacers": [
        "height: 0px",
        "height: 5808px"
      ],
      "rows": [
        "600 | 600 [num] | alpha 600 | true",
        "599 | 599 [num] | foxtrot 599 | false"
      ]
    },
    "record": null,
    "focus": null
  },
  "requests asked of the server": {
    "unrecorded": []
  }
}
? 0
```
