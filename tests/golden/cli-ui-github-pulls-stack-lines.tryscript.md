---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Stack Heading’s Brief Change Line

Each “Stack #N” heading in the Pulls tab shows its stack’s brief change line beside its
label, “Stack #286 · 1 A, 1 M · +5 −0”: the stack’s combined change, its top pull
request’s head against the stack’s base branch, from where they meet, which the server
sums in the repository store (`GET stack-change`). This browserless session runs the
production code that decides what each heading shows,
`builtin_plugins/github/stack-lines.js`, on the server’s own answers, the stack changes
`tests/test_github_stack_change.py` records and the list and stack snapshot the
stack-groups session replays.

`lane` drives the lane alone, with the browser’s idle time, its clock, and when each
read is answered in the session’s hands.
Each step’s `shows` is what each heading shows: `waiting`, the pending placeholder while
the read of its stack is on its way; `shown`, its line; or `none`, no line and no
placeholder.
`asked` is what the step read, one stack at a time when the browser is idle,
and `lane` the lane’s own state.
A heading waits only for its own stack’s read, not for one queued behind another, and a
stack whose answer had no line, or whose read failed, does not wait again.
A line once read is drawn in the paint that draws its heading again, and in a Pulls tab
mounted again in the document, with no request, from the document’s comparison keep,
where it is kept under the stack’s two commits.
A stack is read once for its members and its top’s head as the list’s rows report them:
an hour on with nothing changed, nothing is read; when its top moves it is read again,
and the line it had stays shown meanwhile, and stays shown when that read fails.
A failed read is asked again a minute on, and a 304 says the last answer holds.
A server with no GitHub repository, and one whose repository has no store attached,
refuse every stack at once, and the lane asks one stack a minute on; once the lines’ own
hourly cap is spent no heading waits for a read that will not come.

`heading` mounts the panel over a stand-in for the DOM with the SDK’s own painters and
prints each stack’s heading as drawn: first with no read sent and nothing waiting; then
#290’s read on its way, its heading holding the shell’s pending placeholder and its name
saying the change is pending, while #286’s, queued, holds none; then #290’s unavailable,
its top pull request not cached, and #286’s read on its way; and last #286’s line
arrived, drawn through the SDK’s one component for it (`said`). Its accessible name says
the line in words after the label.
The placeholder is one node across paints, the label stays the node it was, and the line
drawn is the component’s nodes, part for part.

```console
$ node tests/dom/github-pulls-stack-lines-session.js
{
  "lane": [
    {
      "step": "the list draws #286 and #290: nothing is read yet, and no heading waits",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
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
      "step": "the browser is idle: #286's read is sent, and only its heading waits",
      "shows": {
        "Stack #286": "waiting",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "repainted": [
        286
      ],
      "lane": {
        "queue": [
          290
        ],
        "running": 286,
        "sentThisHour": 1,
        "refusedAll": null,
        "recent": []
      }
    },
    {
      "step": "#286's line arrives, and #290's read is sent: its heading waits now",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "waiting"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        286,
        290
      ],
      "lane": {
        "queue": [],
        "running": 290,
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown"
        ]
      }
    },
    {
      "step": "#290's answer: its top is not cached, so its heading shows nothing",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [],
      "repainted": [
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
        "sentThisHour": 0,
        "refusedAll": null,
        "recent": []
      }
    },
    {
      "step": "an hour on, with nothing changed: nothing is read, and no heading waits",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
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
    },
    {
      "step": "#286's top moves: it is read again, and its line stays shown meanwhile",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "lane": {
        "queue": [],
        "running": 286,
        "sentThisHour": 1,
        "refusedAll": null,
        "recent": []
      }
    },
    {
      "step": "its answer arrives: the line it names",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [],
      "repainted": [
        286
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown"
        ]
      }
    },
    {
      "step": "#286's top moves again and the read fails: the line it had stays shown",
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
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #286: failed"
        ]
      }
    },
    {
      "step": "drawn again within the minute: the failed read is not asked again yet",
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
          "Stack #286: failed"
        ]
      }
    },
    {
      "step": "a minute on it is asked again; a 304 says its last answer holds",
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
        "sentThisHour": 3,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged"
        ]
      }
    },
    {
      "step": "the keep let #286's line go and its read failed: no line, and no wait",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "repainted": [
        286,
        286
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 4,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged",
          "Stack #286: failed 500"
        ]
      }
    },
    {
      "step": "a minute on, it is asked again, with no placeholder, and its line is back",
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
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged",
          "Stack #286: failed 500",
          "Stack #286: shown"
        ]
      }
    },
    {
      "step": "#290's top moves: its first read under the new identity waits",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "waiting"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        290
      ],
      "lane": {
        "queue": [],
        "running": 290,
        "sentThisHour": 6,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged",
          "Stack #286: failed 500",
          "Stack #286: shown"
        ]
      }
    },
    {
      "step": "still not cached: nothing, and no wait again",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [],
      "repainted": [
        290
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 6,
        "refusedAll": null,
        "recent": [
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged",
          "Stack #286: failed 500",
          "Stack #286: shown",
          "Stack #290: not_cached"
        ]
      }
    },
    {
      "step": "a server with no repository: one refusal, and no other stack is read",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "repainted": [
        286,
        286
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": "not_github",
        "recent": [
          "Stack #286: not_github"
        ]
      }
    },
    {
      "step": "a server with no repository, drawn again within the minute: nothing is read",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": "not_github",
        "recent": [
          "Stack #286: not_github"
        ]
      }
    },
    {
      "step": "a server with no repository, a minute on: one read, and no heading waits",
      "shows": {
        "Stack #286": "none",
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
        "sentThisHour": 2,
        "refusedAll": "not_github",
        "recent": [
          "Stack #286: not_github",
          "Stack #286: not_github"
        ]
      }
    },
    {
      "step": "a repository with no store attached: one refusal, and no other stack is read",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286"
      ],
      "repainted": [
        286,
        286
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": "no_store",
        "recent": [
          "Stack #286: no_store"
        ]
      }
    },
    {
      "step": "a repository with no store attached, drawn again within the minute: nothing is read",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "none"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": "no_store",
        "recent": [
          "Stack #286: no_store"
        ]
      }
    },
    {
      "step": "a repository with no store attached, a minute on: one read, and no heading waits",
      "shows": {
        "Stack #286": "none",
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
        "sentThisHour": 2,
        "refusedAll": "no_store",
        "recent": [
          "Stack #286: no_store",
          "Stack #286: no_store"
        ]
      }
    },
    {
      "step": "the lines' hourly cap is spent: nothing is read, and no heading waits",
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
        "step": "mounted: no heading waits, since no read is sent; the browser is not idle yet",
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
            "text": "",
            "change": [],
            "name": "Stack #286, 3 pull requests, 2 in this list, 1 under Stack #290"
          }
        },
        "requests": []
      },
      {
        "step": "idle: #290's read is sent, and its heading waits; #286's is queued and does not",
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
            "name": "Stack #290: change pending; 3 pull requests"
          },
          "Stack #286": {
            "heading": [
              "group-heading github-pull-stack-label",
              "github-pulls-stack-change"
            ],
            "label": "Stack #286",
            "text": "",
            "change": [],
            "name": "Stack #286, 3 pull requests, 2 in this list, 1 under Stack #290"
          }
        },
        "requests": [
          "/api/plugin/github/stack-change?number=290"
        ]
      },
      {
        "step": "#290's top is not cached, so it shows nothing; #286's read is sent, and it waits",
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
            "name": "Stack #286: change pending; 3 pull requests, 2 in this list, 1 under Stack #290"
          }
        },
        "requests": [
          "/api/plugin/github/stack-change?number=286"
        ]
      },
      {
        "step": "#286's line arrives in its heading, and #290's shows nothing still",
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
        "requests": []
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
