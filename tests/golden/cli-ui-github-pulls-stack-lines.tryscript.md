---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Stack Heading’s Brief Change Line

Each “Stack #N” heading in the Pulls tab shows its stack’s brief change line beside its
label, “Stack #286 · 1 A, 1 M · +5 −0”: the stack’s combined change, its bottom pull
request’s base against its top pull request’s head, which the server sums in the
repository store (`GET stack-change`). This browserless session runs the production code
that decides what each heading shows, `builtin_plugins/github/stack-lines.js`, on the
server’s own answers, the stack changes `tests/test_github_stack_change.py` records and
the list and stack snapshot the stack-groups session replays.

`lane` drives the lane alone, with the browser’s idle time and its clock in the
session’s hands. Each step’s `shows` is what each heading shows: `waiting`, the pending
placeholder while a read of it is coming; `shown`, its line; or `none`, no line and no
placeholder.
`asked` is what the step read, one stack at a time when the browser is idle,
and `lane` the lane’s own state.
A line once read is drawn in the paint that draws its heading again, and in a Pulls tab
mounted again in the document, with no request, from the document’s comparison keep,
where it is kept under the stack’s two commits.
It is read again once its window passes, and the line it had stays shown meanwhile.
A read that fails shows nothing and is asked again a minute on; a server with no GitHub
repository refuses every stack at once; and once the Pulls tab’s hourly cap is spent no
heading waits for a read that will not come.

`heading` mounts the panel over a stand-in for the DOM with the SDK’s own painters and
prints each stack’s heading as drawn: first holding the shell’s pending placeholder,
then with #286’s line arrived, drawn through the SDK’s one component for it (`said`),
and with #290’s unavailable, its top pull request not cached.
Its accessible name says the line in words after the label.
The placeholder is one node across paints, the label stays the node it was, and the line
drawn is the component’s nodes, part for part.

```console
$ node tests/dom/github-pulls-stack-lines-session.js
{
  "lane": [
    {
      "step": "the list draws #286 and #290: each heading waits, nothing is read yet",
      "shows": {
        "Stack #286": "waiting",
        "Stack #290": "waiting"
      },
      "asked": [],
      "lane": {
        "queue": [
          286,
          290
        ],
        "running": null,
        "sentThisHour": 0,
        "refusedAll": null,
        "recent": []
      }
    },
    {
      "step": "the browser is idle: each is read in turn, #286 summed, #290 not cached",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286",
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        286,
        290
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #290: not_cached"
        ]
      }
    },
    {
      "step": "drawn again: the line in the paint that draws it, and nothing is read",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #290: not_cached"
        ]
      }
    },
    {
      "step": "a Pulls tab mounted again: the line at once, from the keep",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": []
      }
    },
    {
      "step": "its window passed: each is read again, the line it had shown meanwhile",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "waiting"
      },
      "asked": [],
      "lane": {
        "queue": [
          286,
          290
        ],
        "running": null,
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": []
      }
    },
    {
      "step": "the keep let it go and the read failed: no line, and no placeholder",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286",
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        286,
        290
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 4,
        "refusedAll": null,
        "recent": [
          "Stack #286: failed 500",
          "Stack #290: not_cached"
        ]
      }
    },
    {
      "step": "a minute on, the failed read is asked again",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "repainted": [
        286
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 5,
        "refusedAll": null,
        "recent": [
          "Stack #286: failed 500",
          "Stack #290: not_cached",
          "Stack #286: shown"
        ]
      }
    },
    {
      "step": "a server with no repository: one refusal, and no heading waits",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "repainted": [
        null,
        286
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 6,
        "refusedAll": "not_github",
        "recent": [
          "Stack #286: failed 500",
          "Stack #290: not_cached",
          "Stack #286: shown",
          "Stack #286: not_github"
        ]
      }
    },
    {
      "step": "the hour's cap is spent: nothing is read, and no heading waits",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 0,
        "refusedAll": null,
        "recent": []
      }
    }
  ],
  "heading": {
    "steps": [
      {
        "step": "mounted: each heading holds the pending placeholder; the browser is not idle yet",
        "headings": {
          "Stack #290": {
            "heading": [
              "group-heading github-pull-stack-label",
              "github-pulls-stack-change"
            ],
            "label": "Stack #290",
            "text": "",
            "change": [
              {
                "class": "mb-delayed-loading github-pulls-stack-change-pending",
                "aria-hidden": "true",
                "children": [
                  {
                    "class": "tally-pending"
                  }
                ]
              }
            ],
            "name": "Stack #290, 3 pull requests"
          },
          "Stack #286": {
            "heading": [
              "group-heading github-pull-stack-label",
              "github-pulls-stack-change"
            ],
            "label": "Stack #286",
            "text": "",
            "change": [
              {
                "class": "mb-delayed-loading github-pulls-stack-change-pending",
                "aria-hidden": "true",
                "children": [
                  {
                    "class": "tally-pending"
                  }
                ]
              }
            ],
            "name": "Stack #286, 3 pull requests, 2 in this list, 1 under Stack #290"
          }
        },
        "requests": []
      },
      {
        "step": "idle: #286's line arrives in its heading, and #290's cannot be had",
        "headings": {
          "Stack #290": {
            "heading": [
              "group-heading github-pull-stack-label",
              "github-pulls-stack-change"
            ],
            "label": "Stack #290",
            "text": "",
            "change": [],
            "name": "Stack #290, 3 pull requests"
          },
          "Stack #286": {
            "heading": [
              "group-heading github-pull-stack-label",
              "github-pulls-stack-change"
            ],
            "label": "Stack #286",
            "text": "·1 A, 1 M·+5−0",
            "change": [
              {
                "class": "summary-punctuation",
                "aria-hidden": "true",
                "children": [
                  "·"
                ]
              },
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
                              "1"
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
                              "M"
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
                          "+5"
                        ]
                      },
                      {
                        "class": "diff-stat-del",
                        "children": [
                          "−0"
                        ]
                      }
                    ]
                  }
                ]
              }
            ],
            "name": "Stack #286: 1 added, 1 modified; 5 lines added, 0 deleted; 3 pull requests, 2 in this list, 1 under Stack #290"
          }
        },
        "requests": [
          "/api/plugin/github/stack-change?number=290",
          "/api/plugin/github/stack-change?number=286"
        ]
      }
    ],
    "said": {
      "text": "1 A, 1 M · +5 −0",
      "label": "1 added, 1 modified; 5 lines added, 0 deleted"
    }
  },
  "invariants": true
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
