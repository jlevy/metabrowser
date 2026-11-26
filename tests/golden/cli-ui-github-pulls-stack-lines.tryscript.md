---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Stack’s Brief Change Line

Each stack’s Stack Overview row in the Pulls tab shows its stack’s brief change line
beside its words, “Stack Overview · +5”: the lines of the stack’s combined change, its
members’ own changed files accumulated, each file once and their lines summed, which the
server does from the cache (`GET stack-change`); the line counts no files by status
(mb-lqkb), and leaves out a total of zero (mb-efum).
The stack’s own row, its heading, shows the stack’s size and its age instead, “Stack
#286 · 3 pulls”, which are whole from its first paint and wait on no read (mb-tvhs).
This browserless session runs the production code that decides what each stack shows,
`builtin_plugins/github/stack-lines.js`, on the server’s own answers, the stack changes
`tests/test_github_stack_change.py` records and the list and stack snapshot the
stack-groups session replays.

`lane` drives the lane alone, with the browser’s idle time, its clock, and when each
read is answered in the session’s hands.
Each step’s `shows` is what each stack’s line shows: `waiting`, the pending placeholder
while the read of its stack is on its way; `shown`, its line; or `none`, no line and no
placeholder.
`asked` is what the step read, one stack at a time when the browser is idle,
and `lane` the lane’s own state.
A line waits only for its own stack’s read, not for one queued behind another, and a
stack whose answer had no line, or whose read failed, does not wait again.
A line once read is drawn in the paint that draws its row again, and in a Pulls tab
mounted again in the document, with no request, from the document’s comparison keep,
where it is kept under its stack and its revision.
An answer that names members not yet settled, a list missing or read for the head
before, is asked again silently, a minute on and longer each time it still is; a list
the prefetch lane refreshes, or a row reads, makes the stacks that hold it due at once.
A stack is read once for its members and their heads as the list’s rows report them, a
member the list holds no row of taken as unchanged: an hour on with every stack settled,
nothing is read; when a member moves it is read again, and the line it had stays shown
meanwhile, and stays shown when that read fails.
A failed read is asked again a minute on, and a 304 says the last answer holds.
A server with no GitHub repository refuses every stack at once, and the lane asks one
stack a minute on; once the lines’ own hourly cap is spent no line waits for a read that
will not come.

`heading` mounts the panel over a stand-in for the DOM with the SDK’s own painters and
prints each stack as drawn: under `heading`, its own row’s text, age, and accessible
name, and beside it its Stack Overview row’s change slot and name.
First no read is sent and nothing waits; then #290’s read is on its way, its Stack
Overview row holding the shell’s pending placeholder and its name saying the change is
pending, while #286’s, queued, holds none; then #290’s is unavailable, a member’s list
not cached, and #286’s read is on its way; and last #286’s line has arrived, drawn
through the SDK’s one component for it (`said`), its line totals alone.
The row’s accessible name says the line in words after its words and its stack.
Through every step each stack’s heading is as it was first drawn: its count and its age
are there at once, and no read changes them.
Mounted again in a fresh document with a member’s list that could not count a binary
file, the muted “(estimated)” follows the totals, and the name says it.
Mounted again, a fresh document each, with each of `totals`, the line `shows` a total of
zero left out, “−4” for a stack that only deletes lines, as “+5” is one that only adds
them, and both where both are nonzero; a muted “0 lines”, said “no lines changed”, for a
stack that changes none; and “?” for a total not known, beside a zero or a known one.
No line shows a “+0” or a “−0”. The placeholder is one node across paints, the label and
the Stack Overview row’s words stay the nodes they were, and the line drawn is the
component’s nodes, part for part.

`retryMinutes` is when a stack whose answer keeps naming a member not yet settled is
asked again over two and a half hours, the list drawing it each minute: a minute on,
then doubling, then every half hour, the ceiling.

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
      "step": "#290's answer: a member's list is not cached, and it names it: no line, asked again later",
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
          "Stack #290: not_cached, pending"
        ]
      }
    },
    {
      "step": "drawn again within the minute: the line in the paint that draws it, nothing read",
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
          "Stack #290: not_cached, pending"
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
      "step": "a minute on, #290 is asked again, silently; still not cached, it waits longer",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        290
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending"
        ]
      }
    },
    {
      "step": "a filter holds no row of #286's top: nothing is read again",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "none"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 1,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending"
        ]
      }
    },
    {
      "step": "the prefetch lists a member of #290: it is read at once, and its line arrives",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        290
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 2,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending",
          "Stack #290: shown"
        ]
      }
    },
    {
      "step": "an hour on, every stack settled: nothing is read, and no heading waits",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 0,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending",
          "Stack #290: shown"
        ]
      }
    },
    {
      "step": "a member of #286 moves: read again, the line stays; its list is still settling",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
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
        "sentThisHour": 1,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending",
          "Stack #290: shown",
          "Stack #286: shown, pending"
        ]
      }
    },
    {
      "step": "a minute on it is asked again, silently, and the refreshed list settles it",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
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
          "Stack #290: not_cached, pending",
          "Stack #290: shown",
          "Stack #286: shown, pending",
          "Stack #286: shown"
        ]
      }
    },
    {
      "step": "#286's top moves again and the read fails: the line it had stays shown",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
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
          "Stack #290: not_cached, pending",
          "Stack #290: shown",
          "Stack #286: shown, pending",
          "Stack #286: shown",
          "Stack #286: failed"
        ]
      }
    },
    {
      "step": "drawn again within the minute: the failed read is not asked again yet",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
      },
      "asked": [],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 3,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending",
          "Stack #290: shown",
          "Stack #286: shown, pending",
          "Stack #286: shown",
          "Stack #286: failed"
        ]
      }
    },
    {
      "step": "a minute on it is asked again; a 304 says its last answer holds",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
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
        "sentThisHour": 4,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending",
          "Stack #290: shown",
          "Stack #286: shown, pending",
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged"
        ]
      }
    },
    {
      "step": "the keep let the lines go and #286's read failed: no line, and no wait",
      "shows": {
        "Stack #286": "none",
        "Stack #290": "shown 3 files, +3 −0"
      },
      "asked": [
        "GET /api/plugin/github/stack-change?number=286",
        "GET /api/plugin/github/stack-change?number=290"
      ],
      "repainted": [
        286,
        286,
        290,
        290
      ],
      "lane": {
        "queue": [],
        "running": null,
        "sentThisHour": 6,
        "refusedAll": null,
        "recent": [
          "Stack #290: not_cached, pending",
          "Stack #290: shown",
          "Stack #286: shown, pending",
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged",
          "Stack #286: failed 500",
          "Stack #290: shown"
        ]
      }
    },
    {
      "step": "a minute on, #286 is asked again, with no placeholder, and its line is back",
      "shows": {
        "Stack #286": "shown 2 files, +5 −0",
        "Stack #290": "shown 3 files, +3 −0"
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
        "sentThisHour": 7,
        "refusedAll": null,
        "recent": [
          "Stack #290: shown",
          "Stack #286: shown, pending",
          "Stack #286: shown",
          "Stack #286: failed",
          "Stack #286: unchanged",
          "Stack #286: failed 500",
          "Stack #290: shown",
          "Stack #286: shown"
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
        "step": "mounted: no stack waits, since no read is sent; the browser is not idle yet",
        "headings": {
          "Stack #290": {
            "heading": {
              "text": "Stack #290 · 3 pulls",
              "age": "1m",
              "name": "Stack #290, 3 pull requests · 1m"
            },
            "text": "",
            "change": [],
            "name": "Stack Overview, Stack #290"
          },
          "Stack #286": {
            "heading": {
              "text": "Stack #286 · 3 pulls",
              "age": "1m",
              "name": "Stack #286, 3 pull requests, 1 under Stack #290 · 1m"
            },
            "text": "",
            "change": [],
            "name": "Stack Overview, Stack #286"
          }
        },
        "requests": []
      },
      {
        "step": "idle: #290's read is sent, and its Stack Overview row waits; #286's is queued and does not",
        "headings": {
          "Stack #290": {
            "heading": {
              "text": "Stack #290 · 3 pulls",
              "age": "1m",
              "name": "Stack #290, 3 pull requests · 1m"
            },
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
            "name": "Stack Overview, Stack #290: change pending"
          },
          "Stack #286": {
            "heading": {
              "text": "Stack #286 · 3 pulls",
              "age": "1m",
              "name": "Stack #286, 3 pull requests, 1 under Stack #290 · 1m"
            },
            "text": "",
            "change": [],
            "name": "Stack Overview, Stack #286"
          }
        },
        "requests": [
          "/api/plugin/github/stack-change?number=290"
        ]
      },
      {
        "step": "#290 has a member with no list, so it shows nothing; #286's read is sent, and it waits",
        "headings": {
          "Stack #290": {
            "heading": {
              "text": "Stack #290 · 3 pulls",
              "age": "1m",
              "name": "Stack #290, 3 pull requests · 1m"
            },
            "text": "",
            "change": [],
            "name": "Stack Overview, Stack #290"
          },
          "Stack #286": {
            "heading": {
              "text": "Stack #286 · 3 pulls",
              "age": "1m",
              "name": "Stack #286, 3 pull requests, 1 under Stack #290 · 1m"
            },
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
            "name": "Stack Overview, Stack #286: change pending"
          }
        },
        "requests": [
          "/api/plugin/github/stack-change?number=286"
        ]
      },
      {
        "step": "#286's line arrives on its Stack Overview row, and #290's shows nothing still",
        "headings": {
          "Stack #290": {
            "heading": {
              "text": "Stack #290 · 3 pulls",
              "age": "1m",
              "name": "Stack #290, 3 pull requests · 1m"
            },
            "text": "",
            "change": [],
            "name": "Stack Overview, Stack #290"
          },
          "Stack #286": {
            "heading": {
              "text": "Stack #286 · 3 pulls",
              "age": "1m",
              "name": "Stack #286, 3 pull requests, 1 under Stack #290 · 1m"
            },
            "text": "·+5",
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
                    "class": "change-line-stats",
                    "children": [
                      {
                        "class": "diff-stat-add",
                        "children": [
                          "+5"
                        ]
                      }
                    ]
                  }
                ]
              }
            ],
            "name": "Stack Overview, Stack #286: 5 lines added"
          }
        },
        "requests": []
      },
      {
        "step": "a member's list could not count a binary file: “(estimated)” follows the totals",
        "headings": {
          "Stack #286": {
            "heading": {
              "text": "Stack #286 · 3 pulls",
              "age": "1m",
              "name": "Stack #286, 3 pull requests, 1 under Stack #290 · 1m"
            },
            "text": "·+5(estimated)",
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
                    "class": "change-line-stats",
                    "children": [
                      {
                        "class": "diff-stat-add",
                        "children": [
                          "+5"
                        ]
                      }
                    ]
                  }
                ]
              },
              {
                "class": "github-pulls-stack-change-note",
                "children": [
                  "(estimated)"
                ]
              }
            ],
            "name": "Stack Overview, Stack #286: 5 lines added, estimated"
          }
        },
        "requests": [
          "/api/plugin/github/stack-change?number=290",
          "/api/plugin/github/stack-change?number=286"
        ]
      }
    ],
    "said": {
      "text": "+5",
      "label": "5 lines added"
    },
    "totals": [
      {
        "totals": {
          "additions": 0,
          "deletions": 4
        },
        "text": "·−4",
        "shows": [
          "diff-stat-del: −4"
        ],
        "name": "Stack Overview, Stack #286: 4 lines deleted"
      },
      {
        "totals": {
          "additions": 5,
          "deletions": 4
        },
        "text": "·+5−4",
        "shows": [
          "diff-stat-add: +5",
          "diff-stat-del: −4"
        ],
        "name": "Stack Overview, Stack #286: 5 lines added, 4 deleted"
      },
      {
        "totals": {
          "additions": 0,
          "deletions": 0
        },
        "text": "·0 lines",
        "shows": [
          "change-line-none: 0 lines"
        ],
        "name": "Stack Overview, Stack #286: no lines changed"
      },
      {
        "totals": {
          "additions": 0,
          "deletions": null
        },
        "text": "·−?",
        "shows": [
          "diff-stat-del: −?"
        ],
        "name": "Stack Overview, Stack #286: ? lines deleted"
      },
      {
        "totals": {
          "additions": null,
          "deletions": 4
        },
        "text": "·+?−4",
        "shows": [
          "diff-stat-add: +?",
          "diff-stat-del: −4"
        ],
        "name": "Stack Overview, Stack #286: ? lines added, 4 deleted"
      },
      {
        "totals": {
          "additions": null,
          "deletions": null
        },
        "text": "·+?−?",
        "shows": [
          "diff-stat-add: +?",
          "diff-stat-del: −?"
        ],
        "name": "Stack Overview, Stack #286: line counts unknown"
      }
    ]
  },
  "retryMinutes": [
    0,
    1,
    3,
    7,
    15,
    31,
    61,
    91,
    121
  ],
  "invariants": true
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
