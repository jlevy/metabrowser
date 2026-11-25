---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Native Stack’s Page

A stack’s page at `/stack/<n>` draws the stack route’s answer (`pull_stack.py` in the
GitHub plugin): its members, the top member’s head and the base it merges into, and its
comparison from the bottom member’s merge base to the top member’s head, kept to the
files a layer changes.
`tests/test_cli_github_stack_golden.py` records the route’s answers for the GitHub
stand-in’s stacks in `tests/fixtures/github-stack-responses.json`: 70 while its members
have no record and then current, 71, whose top lacks 7, and 72, which is not linear.

This browserless session runs the production `builtin_plugins/github/stack-page.js` on
them.

- `tabs` is the tab each route shows: the front page is Guided Review for a stack whose
  member carries its guide, as 10 carries 70’s, and Changes for one with none, where
  Guided Review’s own address shows Changes too.
  Before the stack is read the front page marks no tab, so none is marked that the
  answer then moves from.
  A tab the page does not have, Files among them, since the stack’s files are its
  header’s Diff summary, shows what the front page shows.
- `guided` is the front page of 70, whose guide 10 carries, while the stack moves: the
  guide shown, the tab, and what the body does after each answer.
  While a member is fetched or the stack cannot be shown, Guided Review and its guide
  stay, as the drawn comparison does, and the guide is mounted again only when the
  reader takes the comparison offered; a description that no longer carries the guide
  turns the front page to Changes.
  `column` is the body’s column (`bodyInColumn`): the reading column, as a pull
  request’s body takes it, except on a drawn Docs or Changes, which take the full pane.
- `comparison` is what a new answer does to the comparison drawn: the first is shown,
  the same one kept, and another offered rather than swapped in under the reader.
- `header` is the page’s header, row by row (`stackHeader`), a pull request’s header
  made of the rows a stack has: its title, the View on GitHub corner, its members top
  first, the merge it makes, the status line while it has something to say, the size
  line, and the Diff summary.
  The first paint draws the members from the stack the Pulls tab knows, titled as its
  lists last read them and authored as the stacks route names them, and holds the
  merge’s row and the size line and summary pending, so each answer after it lands in
  the same rows: a member being fetched keeps its row’s title, the answer names the
  author of a member whose record has one where the stacks route named none (10’s), and
  only the status line comes and goes, as the members 71’s top lacks are said there.
  A stack the Pulls tab does not know is held cold for the quiet period until its answer
  names the members, and one that cannot be shown as one comparison, with none drawn,
  has no size line or summary.
- `drawing` is what the page passes the diff view, as a pull request’s page passes it:
  for the Diff summary only the comparison read and where a file opens, so it starts
  collapsed, as every Diff summary does; and for Docs and Changes the pull request’s
  drawings, with no summary of their own and the first screen’s Markdown held at most
  `CHANGES_FIRST_SCREEN_MS`.
- `said` is the line about members the top lacks, and what the page says for a stack it
  cannot show as one comparison.
- `delays` is the poll’s cadence: soon while a member is being asked for or fetched,
  otherwise at the top member’s probe interval, slowly without one, and not at all out
  of sight (`null`): a hidden page reads the stack again when it is shown.
- `sent` and `rendered` are the controller over a scripted poll: pending, current, an
  unchanged answer, then another comparison (71’s answer standing in for 70 moved).
  Each pending member is asked for at its head, a member with no record as the reader’s
  own open of it (`retry`), and the top member’s automatic ask is sent at its interval
  with the record revision the stack route names, so its answer leaves the record out.
  `failed` lists the members whose fetch ended without a record.
- `recovery` is a read that fails while an answer is drawn, which says so in the page’s
  own words and not the route’s, and then one that finds the drawn answer current again
  (a 304), which ends the failure.
- `cold` is a stack of ten members with no record on a server that fetches eight at once
  and refuses the rest (429). A refused member is asked for again after 2, 4, 8, then 16
  s until its fetch starts.
  One whose fetch ends without a record is named as failed, with a Retry, once a second
  read finds it so, and the reader’s Retry asks for it again.
  Once nothing is being asked for or fetched, the page reads at the slow cadence
  (`delay_after_failure`).
- `one_loop` is a read asked for while one is on its way: it starts no second loop, and
  is made once the first answer is drawn, which leaves one timer.
- `absent_ask` is a member’s fetch the server took while the stack was pending, which
  ends without moving the member once the stack is not linear: the ask ends there as on
  any other answer, and the page reads at the absent stack’s cadence, not every second.
- `ended_race` is the reader’s fetch of a member with no record, one answer showing it
  ended before the record it wrote is read, and the next read having it.
  The page confirms an ended fetch with one more read before it names the member as
  failed, so it names none, and the stack is current a second later.
- `body` is the page’s body over a reader who opens `docs/draft.md` in Changes while the
  stack moves. The file is scrolled to when its diff is first drawn and when the reader
  opens it again, never on a later answer.
  While a member is pending or its fetch has failed, and when another comparison
  arrives, the drawn comparison stays and the header’s status line says why, until the
  reader takes the new one.
  A stack that can no longer be shown as one keeps the comparison drawn; with nothing
  drawn, the body says what is missing.
  `column` is the body’s column, as under `guided`: the full pane once Changes is drawn,
  and the reading column for a notice or a wait with nothing drawn.
- `order` is the header’s order of 71’s members, the top first, as every stack menu
  lists them.

```console
$ node tests/dom/github-stack-page-session.js
{
  "tabs": {
    "guided": {
      "(front)": "guided",
      "guided": "guided",
      "files": "guided",
      "docs": "docs",
      "changes": "changes",
      "conversation": "guided"
    },
    "unguided": {
      "(front)": "changes",
      "guided": "changes",
      "files": "changes",
      "docs": "docs",
      "changes": "changes",
      "conversation": "changes"
    },
    "unread": {
      "(front)": "",
      "guided": "guided",
      "files": "",
      "docs": "docs",
      "changes": "changes",
      "conversation": ""
    }
  },
  "guided": [
    {
      "step": "before any answer",
      "guide": null,
      "tab": "",
      "do": "wait",
      "drawn": null,
      "column": "reading"
    },
    {
      "step": "current",
      "guide": "#10",
      "tab": "guided",
      "do": "mount guided",
      "drawn": "current",
      "column": "reading"
    },
    {
      "step": "a member's push, fetched",
      "guide": "#10",
      "tab": "guided",
      "do": "keep",
      "drawn": "current",
      "column": "reading"
    },
    {
      "step": "current again, another comparison",
      "guide": "#10",
      "tab": "guided",
      "do": "keep",
      "drawn": "current",
      "column": "reading"
    },
    {
      "step": "the reader takes it",
      "guide": "#10",
      "tab": "guided",
      "do": "mount guided",
      "drawn": "other",
      "column": "reading"
    },
    {
      "step": "the stack cannot be shown",
      "guide": "#10",
      "tab": "guided",
      "do": "keep",
      "drawn": "other",
      "column": "reading"
    },
    {
      "step": "the guide's block removed",
      "guide": null,
      "tab": "changes",
      "do": "mount changes",
      "drawn": "other",
      "column": "full pane"
    }
  ],
  "comparison": [
    [
      "nothing drawn, pending",
      "wait"
    ],
    [
      "nothing drawn, current",
      "show"
    ],
    [
      "drawn, the same answer",
      "keep"
    ],
    [
      "drawn, another comparison",
      "offer"
    ],
    [
      "drawn, the stack now absent",
      "keep"
    ]
  ],
  "header": {
    "first_paint": {
      "cold": false,
      "rows": "title, corner, members, merge, size, summary",
      "members": [
        "(unknown) WIP: draft the next page 2/2 · #10",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "pending": {
      "cold": false,
      "rows": "title, corner, members, merge, size, summary",
      "members": [
        "(unknown) WIP: draft the next page 2/2 · #10",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "current": {
      "cold": false,
      "rows": "title, corner, members, merge, size, summary",
      "members": [
        "draft WIP: draft the next page 2/2 · #10 · maintainer",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [],
      "comparison": "drawn"
    },
    "lacking": {
      "cold": false,
      "rows": "title, corner, members, merge, status, size, summary",
      "members": [
        "draft WIP: draft the next page 3/3 · #10 · maintainer",
        "open Count to two in the app 2/3 · #7 · forker",
        "merged Say more in the guide 1/3 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ],
      "comparison": "drawn"
    },
    "unknown_first_paint": {
      "cold": true,
      "rows": "title, corner, merge, size, summary",
      "members": null,
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "unknown_not_linear": {
      "cold": false,
      "rows": "title, corner, members, merge",
      "members": [
        "merged Say more in the guide 2/2 · #8 · maintainer",
        "draft WIP: draft the next page 1/2 · #10 · maintainer"
      ],
      "merge": "guide-more → topic",
      "status": [],
      "comparison": "none"
    }
  },
  "drawing": {
    "summary": {
      "openFile": "function"
    },
    "docs": {
      "comparison": {
        "left": "<base>",
        "right": "<draft_head>",
        "base_policy": "direct",
        "route": "/api/plugin/github/stack-comparison?number=70&left=<base>&right=<draft_head>&base_policy=direct&key=ebfe45cd812c6d00f8d4a921576b31d7&build=<BUILD>&store=<STORE>",
        "image_route": "/api/plugin/github/pull-image?stack=70&left=<base>&right=<draft_head>&store=<STORE>",
        "rendered_route": "/api/plugin/github/pull-rendered-diff?stack=70&left=<base>&right=<draft_head>&store=<STORE>",
        "branch": null
      },
      "summary": false,
      "group": "type:docs",
      "unfold": true,
      "layout": "unified",
      "show": "current",
      "showPreference": "github.docs.show",
      "emptyText": "No documents changed in this stack.",
      "onDocument": "function",
      "markdownHoldMs": 200
    },
    "changes": {
      "comparison": {
        "left": "<base>",
        "right": "<draft_head>",
        "base_policy": "direct",
        "route": "/api/plugin/github/stack-comparison?number=70&left=<base>&right=<draft_head>&base_policy=direct&key=ebfe45cd812c6d00f8d4a921576b31d7&build=<BUILD>&store=<STORE>",
        "image_route": "/api/plugin/github/pull-image?stack=70&left=<base>&right=<draft_head>&store=<STORE>",
        "rendered_route": "/api/plugin/github/pull-rendered-diff?stack=70&left=<base>&right=<draft_head>&store=<STORE>",
        "branch": null
      },
      "summary": false,
      "types": null,
      "onTypes": "function",
      "markdownHoldMs": 200
    }
  },
  "said": {
    "lacking": "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them.",
    "lacking_none": null,
    "two_lacking": "The top of this stack does not contain #7 and #9, so this view leaves out each one’s changes. Open each to see them.",
    "not_linear": "This stack’s changes cannot be shown together. Open each pull request for its changes.",
    "unknown": "This stack cannot be shown."
  },
  "delays": {
    "pending_visible": 1000,
    "pending_none_asked": 30000,
    "current_visible": 5000,
    "current_hidden": null
  },
  "sent": [
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70"
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 8,
        "retry": true
      }
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "retry": true
      }
    },
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70",
      "etag": "\"pending\""
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "held": "1f5deb5aaaba5bf66d652ec3295bbd460eb6f34d9ffd5aef32e7f077f76294ad"
      }
    },
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70",
      "etag": "\"current\""
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "held": "1f5deb5aaaba5bf66d652ec3295bbd460eb6f34d9ffd5aef32e7f077f76294ad"
      }
    },
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70",
      "etag": "\"current\""
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "held": "1f5deb5aaaba5bf66d652ec3295bbd460eb6f34d9ffd5aef32e7f077f76294ad"
      }
    }
  ],
  "rendered": [
    {
      "state": "pending",
      "pending": [
        8,
        10
      ],
      "lacking": [],
      "comparison": "wait",
      "error": null,
      "failed": []
    },
    {
      "state": "current",
      "pending": [],
      "lacking": [],
      "comparison": "show",
      "error": null,
      "failed": []
    },
    {
      "state": "current",
      "pending": [],
      "lacking": [
        7
      ],
      "comparison": "offer",
      "error": null,
      "failed": []
    }
  ],
  "recovery": [
    {
      "state": "current",
      "error": null
    },
    {
      "state": "current",
      "error": "Could not read this stack."
    },
    {
      "state": "current",
      "error": null
    }
  ],
  "cold": {
    "asked": [
      "0s #100 retry 202",
      "0s #101 retry 202",
      "0s #102 retry 202",
      "0s #103 retry 202",
      "0s #104 retry 202",
      "0s #105 retry 202",
      "0s #106 retry 202",
      "0s #107 retry 202",
      "0s #108 retry 429",
      "0s #109 retry 429",
      "2s #108 retry 429",
      "2s #109 retry 429",
      "6s #108 retry 202",
      "6s #109 retry 202",
      "10s #109 retry 202"
    ],
    "rendered": [
      {
        "at": "0s",
        "pending": [
          100,
          101,
          102,
          103,
          104,
          105,
          106,
          107,
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "1s",
        "pending": [
          100,
          101,
          102,
          103,
          104,
          105,
          106,
          107,
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "2s",
        "pending": [
          100,
          101,
          102,
          103,
          104,
          105,
          106,
          107,
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "3s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "6s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "7s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "8s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "9s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "10s",
        "pending": [
          109
        ],
        "failed": [
          109
        ]
      },
      {
        "at": "10s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "10s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "11s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "12s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "13s",
        "pending": [],
        "failed": []
      }
    ],
    "delay_after_failure": 30000
  },
  "one_loop": {
    "during": {
      "gets": 1,
      "timers": 0
    },
    "after_first": {
      "gets": 2,
      "timers": 0
    },
    "after_second": {
      "gets": 2,
      "timers": 1
    }
  },
  "absent_ask": {
    "asked": [
      "0s #8 202"
    ],
    "reads": [
      "0s pending",
      "1s pending",
      "2s pending",
      "3s absent",
      "33s absent"
    ]
  },
  "ended_race": [
    {
      "at": "0s",
      "state": "pending",
      "failed": []
    },
    {
      "at": "1s",
      "state": "pending",
      "failed": []
    },
    {
      "at": "2s",
      "state": "current",
      "failed": []
    }
  ],
  "body": [
    {
      "step": "opened a file, nothing read",
      "do": "wait",
      "drawn": null,
      "column": "reading",
      "notices": []
    },
    {
      "step": "pending",
      "do": "notice",
      "text": "Fetching #8 and #10 before the stack can be shown.",
      "drawn": null,
      "column": "reading",
      "notices": []
    },
    {
      "step": "current",
      "do": "mount changes",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "current, mounted",
      "do": "scroll",
      "file": "docs/draft.md",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "current again, top revision moved",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "the reader opens the file again",
      "do": "scroll",
      "file": "docs/draft.md",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "a member added on top, pending",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": [
        "Fetching #11 before its new comparison can be shown."
      ]
    },
    {
      "step": "its fetch failed",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": [
        "Could not fetch #11 from GitHub. [retry]"
      ]
    },
    {
      "step": "it arrived: another comparison",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": [
        "This stack has changed since its comparison was drawn. [take]",
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ]
    },
    {
      "step": "the reader takes it",
      "do": "mount changes",
      "drawn": "other",
      "column": "full pane",
      "notices": [
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ]
    },
    {
      "step": "the stack can no longer be shown as one",
      "do": "keep",
      "drawn": "other",
      "column": "full pane",
      "notices": [
        "This stack’s changes cannot be shown together. Open each pull request for its changes."
      ]
    },
    {
      "step": "the reader opens Docs",
      "do": "mount docs",
      "drawn": "other",
      "column": "full pane",
      "notices": [
        "This stack’s changes cannot be shown together. Open each pull request for its changes."
      ]
    },
    {
      "step": "nothing drawn, a member's fetch failed",
      "do": "notice",
      "text": "Fetching #8 before the stack can be shown. Could not fetch #10 from GitHub.",
      "retry": true,
      "drawn": null,
      "column": "reading",
      "notices": []
    },
    {
      "step": "nothing drawn, not linear",
      "do": "notice",
      "text": "This stack’s changes cannot be shown together. Open each pull request for its changes.",
      "drawn": null,
      "column": "reading",
      "notices": []
    }
  ],
  "order": [
    10,
    7,
    8
  ]
}
? 0
```
