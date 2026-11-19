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
The line’s `words`, hidden, say it in words, and its row is described by them
(`aria-describedby`); `chevron` is the way the line’s chevron turns.

Run alone, the session holds every part’s invariants and says how many steps each took;
`lane`, `row`, `tree`, and `focus` print each part.

```console
$ node tests/dom/github-pulls-row-lines-session.js
{
  "steps": {
    "lane": 23,
    "row": 2,
    "tree": 20,
    "focus": 8
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
      "step": "#106 is pushed again: its line stays shown while it is read again",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
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
      "step": "the request had no room for #106's list (deferred): its line stays, and the next request reads it",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-files-summary?numbers=106"
      ],
      "repainted": [
        "106"
      ],
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
      "step": "the next request reads it: shown",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "none",
        "#103": "none"
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
      "step": "the lane takes the ask for #104's files: it waits",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "waiting",
        "#103": "none"
      },
      "asked": [],
      "repainted": [
        "104"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [
          104
        ],
        "refusedAll": false
      }
    },
    {
      "step": "the panel stops following the lane: nothing more is read",
      "shows": {
        "#106": "shown 249 files: 3 added, 243 modified, 1 removed, 2 renamed; +1093 −493",
        "#105": "shown 1 file: 1 modified; +3 −1",
        "#104": "waiting",
        "#103": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "awaiting": [
          104
        ],
        "refusedAll": false
      }
    },
    {
      "step": "a minute on, #104 is read again and leaves the placeholder: its list is not cached",
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
      "step": "read again from nothing: #103's list is still filling",
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
      "step": "#103's tree reads that refresh's list: nothing more is read",
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
              "github-pulls-change-line",
              "github-pulls-change-words"
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
            "words": "Changed files",
            "chevron": "collapsed"
          },
          "#105": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line",
              "github-pulls-change-words"
            ],
            "text": "",
            "words": "Changed files",
            "chevron": "collapsed"
          },
          "#104": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line",
              "github-pulls-change-words"
            ],
            "text": "",
            "words": "Changed files",
            "chevron": "collapsed"
          },
          "#103": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line",
              "github-pulls-change-words"
            ],
            "text": "",
            "words": "Changed files",
            "chevron": "collapsed"
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
              "github-pulls-change-line",
              "github-pulls-change-words"
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
                            "class": "summary-status-count file-change-status",
                            "children": [
                              {
                                "class": "summary-number",
                                "children": [
                                  "3"
                                ]
                              },
                              " A"
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
                            "class": "summary-status-count file-change-status",
                            "children": [
                              {
                                "class": "summary-number",
                                "children": [
                                  "1"
                                ]
                              },
                              " D"
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
                            "class": "summary-status-count file-change-status",
                            "children": [
                              {
                                "class": "summary-number",
                                "children": [
                                  "243"
                                ]
                              },
                              " M"
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
                            "class": "summary-status-count file-change-status",
                            "children": [
                              {
                                "class": "summary-number",
                                "children": [
                                  "2"
                                ]
                              },
                              " R"
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
            "words": "Changed files: 3 added, 1 deleted, 243 modified, 2 renamed; 1,093 lines added, 493 deleted",
            "chevron": "collapsed"
          },
          "#105": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line",
              "github-pulls-change-words"
            ],
            "text": "1 M·+3−1",
            "words": "Changed files: 1 modified; 3 lines added, 1 deleted",
            "chevron": "collapsed"
          },
          "#104": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line",
              "github-pulls-change-words"
            ],
            "text": "",
            "words": "Changed files",
            "chevron": "collapsed"
          },
          "#103": {
            "parts": [
              "github-pulls-toggle",
              "github-pulls-change-line",
              "github-pulls-change-words"
            ],
            "text": "",
            "words": "Changed files",
            "chevron": "collapsed"
          }
        },
        "requests": [
          "/api/plugin/github/pull-files-summary?numbers=106,105,104,103,102,101,100,99,98,…"
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

`tree` goes on in the same panel and prints, after each press and key, each item’s row
and the change line under it: the row’s role, level, place, expansion, what it owns, and
what describes it; the change line’s chevron; the Tab stop; and focus.
A pull request is one item of three lines, one stop of the tree (mb-1z7j): its row, the
link, is the tree’s item, owns its files, and alone says whether they are open.
Its change line, the line that carries the toggle, is the pointer’s alone: no stop of
the tree’s, and hidden from assistive technology, so the tree’s children are its rows
and their groups, as ARIA’s tree allows.
No row’s files are open by default.
A press on a row’s title, number’s line, or state icon opens it and expands nothing; a
press anywhere on its change line, its chevron or its values, opens or closes its files,
opens no page, and leaves the focus on the item: the rule for a row with a disclosure
toggle, which the invariants hold at every step (`pressed`). Up and Down walk the pull
requests as wholes and expand nothing, whether a row’s files are open or not.
On a row, Space opens and closes its files, Right opens them and then goes into them,
Left closes them and then goes to its stack’s row, and Enter opens the pull request.

```console
$ node tests/dom/github-pulls-row-lines-session.js tree
{
  "tree": [
    {
      "step": "the collapsed default: no row's files are open, and no list was read",
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · described by github-pull-change-106 · Tab stop",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "requests": []
    },
    {
      "step": "a press on #106's title opens it, and its files stay closed",
      "pressed": {
        "item": 106,
        "on": "title"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · described by github-pull-change-106 · Tab stop",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#106"
      ]
    },
    {
      "step": "a press on #105's number's line opens it, and its files stay closed",
      "pressed": {
        "item": 105,
        "on": "number's line"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105 · Tab stop",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#105"
      ]
    },
    {
      "step": "a press on #106's state icon opens it again, and its files stay closed",
      "pressed": {
        "item": 106,
        "on": "state icon"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · described by github-pull-change-106 · Tab stop",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#106"
      ]
    },
    {
      "step": "a press on #106's chevron opens its files, opens no page, and focuses its item",
      "pressed": {
        "item": 106,
        "on": "chevron"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-files-106 · described by github-pull-change-106 · Tab stop · focused",
        "  #106's change line · hidden · chevron expanded · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=106&offset=0"
      ]
    },
    {
      "step": "a press on the values of its change line closes them: the whole line carries the toggle",
      "pressed": {
        "item": 106,
        "on": "change line"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106 · Tab stop · focused",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    },
    {
      "step": "a press on the change line itself, past its values, opens them again",
      "pressed": {
        "item": 106,
        "on": "change line"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded true · owns github-pull-files-106 · described by github-pull-change-106 · Tab stop · focused",
        "  #106's change line · hidden · chevron expanded · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=106&offset=0"
      ]
    },
    {
      "step": "and closes them",
      "pressed": {
        "item": 106,
        "on": "change line"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106 · Tab stop · focused",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    },
    {
      "step": "Down walks to #105, a whole item, which opens and expands nothing",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#105"
      ]
    },
    {
      "step": "Down again to #104: nothing expands",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104 · Tab stop · focused",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#104"
      ]
    },
    {
      "step": "Up back to #105",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#105"
      ]
    },
    {
      "step": "Space on #105 (the handle's toggleFiles) opens its files in place, and keeps the focus",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron expanded · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=105&offset=0"
      ]
    },
    {
      "step": "Space again closes them",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    },
    {
      "step": "Enter opens #105 again, and expands nothing",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#105"
      ]
    },
    {
      "step": "Right opens #105's files, as on a folder",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron expanded · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=105&offset=0"
      ]
    },
    {
      "step": "Right again, its files not yet listed, has no file to go to: the focus stays",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron expanded · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=105&offset=0"
      ]
    },
    {
      "step": "Down from #105, its files open, goes on to #104, a whole item: the files are Right's",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-files-105 · described by github-pull-change-105",
        "  #105's change line · hidden · chevron expanded · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104 · Tab stop · focused",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#104"
      ]
    },
    {
      "step": "Up back to #105, its files still open",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded true · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron expanded · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ],
      "opened": [
        "#105"
      ]
    },
    {
      "step": "Left closes #105's files, as on a folder",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    },
    {
      "step": "Left again, on a pull request in no stack, goes nowhere, and is the list's",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop · focused",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · described by github-pull-change-103",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    }
  ],
  "invariants": true
}
? 0
```

`focus` goes on from there.
A press on #103’s change line focuses #103 while #105’s page is open, and each poll then
settles the list’s Tab stop back on #105, the current pull request, and leaves the focus
on #103. Left, Right, and Enter still act on #103, the item with focus, as Space does,
so every key acts on the same item.

```console
$ node tests/dom/github-pulls-row-lines-session.js focus
{
  "focus": [
    {
      "step": "a press on #103's change line opens its files and focuses #103, while #105's page is open",
      "pressed": {
        "item": 103,
        "on": "change line"
      },
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-files-103 · described by github-pull-change-103 · Tab stop · focused",
        "  #103's change line · hidden · chevron expanded · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=103&offset=0"
      ]
    },
    {
      "step": "a poll: the Tab stop goes back to #105, and focus stays on #103",
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-files-103 · described by github-pull-change-103 · focused",
        "  #103's change line · hidden · chevron expanded · no stop"
      ]
    },
    {
      "step": "Left closes #103's files: the item with focus, not the Tab stop",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · owns github-pull-files-103 · described by github-pull-change-103 · Tab stop · focused",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    },
    {
      "step": "a poll again: the Tab stop goes back to #105",
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded false · owns github-pull-files-103 · described by github-pull-change-103 · focused",
        "  #103's change line · hidden · chevron collapsed · no stop"
      ]
    },
    {
      "step": "Right opens #103's files again",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-files-103 · described by github-pull-change-103 · Tab stop · focused",
        "  #103's change line · hidden · chevron expanded · no stop"
      ],
      "requests": [
        "/api/plugin/github/pull-files?number=103&offset=0"
      ]
    },
    {
      "step": "a poll again",
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105 · Tab stop",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-files-103 · described by github-pull-change-103 · focused",
        "  #103's change line · hidden · chevron expanded · no stop"
      ]
    },
    {
      "step": "Enter opens #103, the item with focus",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-files-103 · described by github-pull-change-103 · Tab stop · focused",
        "  #103's change line · hidden · chevron expanded · no stop"
      ],
      "opened": [
        "#103"
      ]
    },
    {
      "step": "Tab reaches #103's row, and Enter opens it: nothing expands",
      "handled": true,
      "tree": [
        "#106 · treeitem · level 1 · 1/102 · expanded false · owns github-pull-files-106 · described by github-pull-change-106",
        "  #106's change line · hidden · chevron collapsed · no stop",
        "#105 · treeitem · level 1 · 2/102 · expanded false · owns github-pull-files-105 · described by github-pull-change-105",
        "  #105's change line · hidden · chevron collapsed · no stop",
        "#104 · treeitem · level 1 · 3/102 · expanded false · described by github-pull-change-104",
        "  #104's change line · hidden · chevron collapsed · no stop",
        "#103 · treeitem · level 1 · 4/102 · expanded true · owns github-pull-files-103 · described by github-pull-change-103 · Tab stop · focused",
        "  #103's change line · hidden · chevron expanded · no stop"
      ],
      "opened": [
        "#103"
      ]
    }
  ],
  "invariants": true
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
