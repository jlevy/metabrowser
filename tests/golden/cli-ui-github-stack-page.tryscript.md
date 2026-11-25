---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Native Stack’s Page

A stack’s page at `/stack/<n>` draws the stack route’s answer (`pull_stack.py` in the
GitHub plugin): its members, its comparison from the bottom member’s merge base to the
top member’s head, kept to the files a layer changes, and each file’s layers.
`tests/test_cli_github_stack_golden.py` records the route’s answers for the GitHub
stand-in’s stacks in `tests/fixtures/github-stack-responses.json`: 70 while its members
have no record and then current, 71, whose top lacks 7, and 72, which is not linear.

This browserless session runs the production `builtin_plugins/github/stack-page.js` on
them.

- `tabs` is the tab each route shows: the front page is Files until a stack has a guide,
  and a tab the page does not have shows Files.
- `comparison` is what a new answer does to the comparison drawn: the first is shown,
  the same one kept, and another offered rather than swapped in under the reader.
- `marks` are a file’s layer marks, each opening the file in that layer’s Changes; a
  file no layer changes has none.
- `said` is the line about members the top lacks, and what the page says for a stack it
  cannot show as one comparison.
- `delays` is the poll’s cadence: soon while a member is pending, at the top member’s
  probe interval in sight, and slowly out of sight.
- `sent` and `rendered` are the controller over a scripted poll: pending, current, an
  unchanged answer, then another comparison (71’s answer standing in for 70 moved).
  Each pending member is asked for once at its head, and the top member’s automatic ask
  is sent at its interval with the record revision the stack route names, so its answer
  leaves the record out.

```console
$ node tests/dom/github-stack-page-session.js
{
  "tabs": {
    "(front)": "files",
    "files": "files",
    "docs": "docs",
    "changes": "changes",
    "guided": "files"
  },
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
  "marks": {
    "docs/draft.md": [
      {
        "number": 10,
        "path": "docs/draft.md",
        "text": "2/2",
        "label": "Layer 2 of 2, #10: this file's changes there",
        "href": "/pull/10/files/docs/draft.md"
      }
    ],
    "README.md": []
  },
  "said": {
    "lacking": "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them.",
    "lacking_none": null,
    "two_lacking": "The top of this stack does not contain #7 and #9, so this view leaves out each one's changes. Open each to see them.",
    "not_linear": "The bottom pull request's base is not in the top one's history, so this stack has no single comparison. Open each pull request for its changes.",
    "unknown": "This stack cannot be shown."
  },
  "delays": {
    "pending_visible": 1000,
    "current_visible": 5000,
    "current_hidden": 30000
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
        "number": 8
      }
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10
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
        "held": "b61b65443f1b94641b404dc8f04f65cdc54e53ccda7d5bdb50f0628bc0737ff4"
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
        "held": "b61b65443f1b94641b404dc8f04f65cdc54e53ccda7d5bdb50f0628bc0737ff4"
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
        "held": "b61b65443f1b94641b404dc8f04f65cdc54e53ccda7d5bdb50f0628bc0737ff4"
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
      "error": null
    },
    {
      "state": "current",
      "pending": [],
      "lacking": [],
      "comparison": "show",
      "error": null
    },
    {
      "state": "current",
      "pending": [],
      "lacking": [
        7
      ],
      "comparison": "offer",
      "error": null
    }
  ]
}
? 0
```
