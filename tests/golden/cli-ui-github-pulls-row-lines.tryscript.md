---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Pulls Row’s Brief Change Line

Each pull request’s row in the Pulls tab has a third line, its brief change line, “3 A,
1 D, 243 M, 2 R · +1,093 −493”, with no file total, and the chevron for its changed
files before it (mb-d0a3, mb-h0ml). The line is what the row’s own cached list of
changed files sums to, the list its chevron discloses, which the server answers for
every row the list draws in one request (`GET pull-files-summary`) from the cache alone.
This browserless session runs the production code that decides what each row’s third
line shows, `builtin_plugins/github/row-lines.js`, on the server’s own answers, the
summaries `tests/test_github_pull_files_summary.py` records and the list the panel
session replays.

`lane` drives the lane alone, with the browser’s idle time and its clock in the
session’s hands. Each step’s `shows` is what each row shows: `waiting`, the pending
placeholder while a read of it is coming or its list is being listed; `shown`, its line;
or `none`, no line and no placeholder.
`asked` is what the step read, all the rows drawn in one request when the browser is
idle, and `lane` the lane’s own state.
A line once read is drawn in the paint that draws its row again, and in a Pulls tab
mounted again in the document, with no request.
It is read again only when something says its list changed: the prefetch lane listed it,
the row’s head moved, or its own tree read a list of another refresh.
A row whose list the lane was asked to list, or whose answer says another refresh is
listing it, waits; a read that fails shows nothing and is asked again a minute on; and a
server with no GitHub repository answers once for every row.

`row` mounts the panel over a stand-in for the DOM with the SDK’s own painters and
prints each row’s third line as drawn: first holding the shell’s pending placeholder,
then with #106’s and #105’s lines arrived, drawn through the SDK’s one component for it
(`said`), and #104 and #103 with none.
Its item’s accessible name says the line in words.
Then `tree` prints, after each press and key, each row and its change line, the row’s
one child item, with their roles, levels, places, expansion, Tab stop, and focus.
No row’s files are open by default.
A press on a row’s title opens it and expands nothing; a press on its chevron or its
line opens or closes its files and opens no page.
Up and Down walk the rows and expand nothing.
Right goes to a row’s change line, where Enter and Space open and close its files, Right
opens them, Left closes them and then goes back to the row, Up goes back to the row, and
Down goes into the open files, or on to the next row.

Run alone, the session holds every part’s invariants and says how many steps each took;
`lane` and `row` print each part.

```console
$ node tests/dom/github-pulls-row-lines-session.js
{
  "steps": {
    "lane": 15,
    "row": 22
  },
  "invariants": true
}
? 0
```

```console
$ node tests/dom/github-pulls-row-lines-session.js lane
{
  "lane": [
    {
      "step": "the list draws #106 to #103: each row waits, and nothing is read yet",
      "shows": {
        "#106": "waiting",
        "#105": "waiting",
        "#104": "waiting",
        "#103": "waiting"
      },
      "asked": [],
      "lane": {
        "wanted": [
          106,
          105,
          104,
          103
        ],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "the browser is idle: one read for all four; #106 and #105 are summed, #104 has no list, and #103's is still filling",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106,105,104,103"
      ],
      "repainted": [
        "106,105,104,103"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "drawn again: each line in the paint that draws it, and nothing is read",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "a Pulls tab mounted again: the lines at once, from the document's index",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "the prefetch lane takes the ask to list #104's and #103's files: both wait",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "waiting",
        "#103": "waiting"
      },
      "asked": [],
      "repainted": [
        "104,103"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [
          104,
          103
        ],
        "refusedAll": false
      }
    },
    {
      "step": "the lane's report says it listed them: both are read again in one request, and both are shown",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "shown 2 files: 1 added, 1 modified; +16 −2",
        "#103": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=104,103"
      ],
      "repainted": [
        "104,103",
        "104,103"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "#106 is pushed, its head moves: it is read again, its line shown meanwhile",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "shown 2 files: 1 added, 1 modified; +16 −2",
        "#103": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493"
      },
      "asked": [],
      "lane": {
        "wanted": [
          106
        ],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "and once read, shown again",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "shown 2 files: 1 added, 1 modified; +16 −2",
        "#103": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106"
      ],
      "repainted": [
        "106"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "#105's tree reads a list of another refresh: its line is read again",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "shown 2 files: 1 added, 1 modified; +16 −2",
        "#103": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=105"
      ],
      "repainted": [
        "105"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "its tree reads the same refresh's list: nothing is read",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "shown 2 files: 1 added, 1 modified; +16 −2",
        "#103": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "a row whose list another's refresh is listing waits for it, and nothing more is read",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "waiting",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106,105,104,103"
      ],
      "repainted": [
        "106,105,104,103"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "a minute on, it is asked again: no list, so no line and no placeholder",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=104"
      ],
      "repainted": [
        "104"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "the read fails: no line and no placeholder",
      "shows": {
        "#106": "none",
        "#105": "none",
        "#104": "none",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106,105,104,103"
      ],
      "repainted": [
        "106,105,104,103"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "a minute on, the failed read is asked again",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106,105,104,103"
      ],
      "repainted": [
        "106,105,104,103"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": false
      }
    },
    {
      "step": "a server with no repository: one answer, and no row waits",
      "shows": {
        "#106": "none",
        "#105": "none",
        "#104": "none",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106,105,104,103"
      ],
      "repainted": [
        "every row"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [],
        "refusedAll": true
      }
    }
  ],
  "invariants": true
}
? 0
```

```console
$ node tests/dom/github-pulls-row-lines-session.js row
{
  "row": {
    "steps": [
      {
        "step": "mounted: each row's third line holds the pending placeholder; the browser is not idle yet",
        "lines": {
          "#106": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "",
            "line": [
              {
                "class": "mb-delayed-loading github-pulls-change-pending",
                "aria-hidden": "true",
                "children": [
                  {
                    "class": "tally-pending"
                  }
                ]
              }
            ],
            "name": "Changed files",
            "expanded": "false"
          },
          "#105": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "",
            "name": "Changed files",
            "expanded": "false"
          },
          "#104": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "",
            "name": "Changed files",
            "expanded": "false"
          },
          "#103": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "",
            "name": "Changed files",
            "expanded": "false"
          }
        },
        "requests": []
      },
      {
        "step": "idle: one read for the rows drawn; #106's and #105's lines arrive, and #104 and #103 have none",
        "lines": {
          "#106": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "3 A, 1 D, 243 M, 2 R·+1,093−493",
            "line": [
              {
                "class": "change-line",
                "children": [
                  {
                    "class": "change-line-group",
                    "children": [
                      {
                        "class": "change-line-statuses",
                        "children": [
                          {
                            "class": "summary-number",
                            "children": [
                              "3"
                            ]
                          },
                          " ",
                          {
                            "class": "file-change-status",
                            "children": [
                              "A"
                            ]
                          },
                          {
                            "class": "summary-punctuation",
                            "children": [
                              ","
                            ]
                          },
                          " ",
                          {
                            "class": "summary-number",
                            "children": [
                              "1"
                            ]
                          },
                          " ",
                          {
                            "class": "file-change-status",
                            "children": [
                              "D"
                            ]
                          },
                          {
                            "class": "summary-punctuation",
                            "children": [
                              ","
                            ]
                          },
                          " ",
                          {
                            "class": "summary-number",
                            "children": [
                              "243"
                            ]
                          },
                          " ",
                          {
                            "class": "file-change-status",
                            "children": [
                              "M"
                            ]
                          },
                          {
                            "class": "summary-punctuation",
                            "children": [
                              ","
                            ]
                          },
                          " ",
                          {
                            "class": "summary-number",
                            "children": [
                              "2"
                            ]
                          },
                          " ",
                          {
                            "class": "file-change-status",
                            "children": [
                              "R"
                            ]
                          }
                        ]
                      },
                      {
                        "class": "summary-punctuation",
                        "aria-hidden": "true",
                        "children": [
                          "·"
                        ]
                      }
                    ]
                  },
                  {
                    "class": "change-line-stats",
                    "children": [
                      {
                        "class": "diff-stat-add",
                        "children": [
                          "+1,093"
                        ]
                      },
                      {
                        "class": "diff-stat-del",
                        "children": [
                          "−493"
                        ]
                      }
                    ]
                  }
                ]
              }
            ],
            "name": "Changed files: 3 added, 1 deleted, 243 modified, 2 renamed; 1,093 lines added, 493 deleted",
            "expanded": "false"
          },
          "#105": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "1 M·+3−1",
            "name": "Changed files: 1 modified; 3 lines added, 1 deleted",
            "expanded": "false"
          },
          "#104": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "",
            "name": "Changed files",
            "expanded": "false"
          },
          "#103": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line"
            ],
            "text": "",
            "name": "Changed files",
            "expanded": "false"
          }
        },
        "requests": [
          "/api/plugin/github/pull-files-summary?numbers=106,105,104,103,102,101,100,99,98,…"
        ]
      },
      {
        "step": "the collapsed default: no row's files are open, and no list was read",
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106 · Tab stop",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "requests": []
      },
      {
        "step": "a press on #106's title opens it, and its files stay closed",
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106 · Tab stop",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#106"
        ]
      },
      {
        "step": "a press on its chevron opens its files, and opens no page",
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106 · Tab stop",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded true · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "requests": [
          "/api/plugin/github/pull-files?number=106&offset=0"
        ]
      },
      {
        "step": "a press on its change line closes them",
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106 · Tab stop",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Down walks to #105, which opens, and expands nothing",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop · focused",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#105"
        ]
      },
      {
        "step": "Down again to #104: nothing expands",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104 · Tab stop · focused",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#104"
        ]
      },
      {
        "step": "Up back to #105",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop · focused",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#105"
        ]
      },
      {
        "step": "Right on #105 goes to its change line, and opens nothing",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Enter on the change line opens its files",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded true · owns github-pull-files-105 · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "requests": [
          "/api/plugin/github/pull-files?number=105&offset=0"
        ]
      },
      {
        "step": "Enter again closes them",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105 · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Space on it (the handle's toggleFiles) opens them",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded true · owns github-pull-files-105 · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "requests": [
          "/api/plugin/github/pull-files?number=105&offset=0"
        ]
      },
      {
        "step": "Left closes them, and keeps the change line",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105 · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Right opens them again",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded true · owns github-pull-files-105 · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "requests": [
          "/api/plugin/github/pull-files?number=105&offset=0"
        ]
      },
      {
        "step": "Down from the open change line, its files not yet listed, goes on to #104, which opens",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded true · owns github-pull-files-105",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104 · Tab stop · focused",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#104"
        ]
      },
      {
        "step": "Up back to #105, which opens",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop · focused",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded true · owns github-pull-files-105",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#105"
        ]
      },
      {
        "step": "Right to its change line, then Left: its files close",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105 · focused",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Left again goes back to #105's row",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop · focused",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Right, then Up from the change line: back to #105's row",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105 · Tab stop · focused",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ]
      },
      {
        "step": "Right, then Down from its closed change line: on to #104, which opens",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104 · Tab stop · focused",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#104"
        ]
      },
      {
        "step": "Tab reaches #103's row, and Enter opens it: nothing expands",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-change-106",
          "  #106's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-106",
          "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-change-105",
          "  #105's change line · treeitem · level 2 · 1/1 · expanded false · owns github-pull-files-105",
          "#104 · treeitem · level 1 · 3/102 · expanded true · owns github-pull-change-104",
          "  #104's change line · treeitem · level 2 · 1/1 · expanded false",
          "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-change-103 · Tab stop · focused",
          "  #103's change line · treeitem · level 2 · 1/1 · expanded false"
        ],
        "opened": [
          "#103"
        ]
      }
    ],
    "said": {
      "text": "3 A, 1 D, 243 M, 2 R · +1,093 −493",
      "label": "3 added, 1 deleted, 243 modified, 2 renamed; 1,093 lines added, 493 deleted"
    }
  },
  "invariants": true
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
