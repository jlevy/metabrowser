---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Pulls Tab Grouped by Stack

The Pulls tab always groups a native stack’s pull requests under a “Stack #N” row, open
by default. This browserless session runs the production code that decides it on the
server’s own answers, the lists and the stack snapshots
`tests/test_github_pulls_panel_session.py` records:
`builtin_plugins/github/pull-stacks.js` for how the rows group and what a badge says,
and the Pulls controller in `builtin_plugins/github/pulls-panel.js` for the rows the
list draws and the keys that walk them.

Each stack with a pull request in the list has a row, and under it the stack’s pull
requests in the list, top of the stack first, as the pull request page’s stack menu
lists them.
The stacks come in the order of their first pull request in the list, and the
pull requests in no stack follow them, in the list’s order.
A pull request in two stacks sits once, under the first, and its badge names the other
by the Layers glyph, written ⧉ here, before its number; the other stack’s row still
counts it, and its tip says where it sits.
Until stacks are known for the list’s own GitHub account, and while none of the list’s
pull requests is in one, the list stays flat; there is no option.
A stack’s row is a row of the tree, as a folder is: J and K stop on it and open nothing,
Enter opens or closes it, Right opens it or goes to its first pull request, and Left
closes it, or from a pull request in it goes to it.

Each step’s `rows` are what a reader sees: a stack’s row with its count, place, and tip,
its pull requests a level in with their places, and then the ends of the rest.
After a walk, `read ahead after the last open` is what the open asks to read next: its
neighbours as drawn, a stack’s row passed over, then the first pull requests drawn.
`mounted` mounts the panel over a stand-in for the DOM and drives its handle, as Space,
Right, and Left reach it, and a press on a stack’s row, printing the tree’s roles,
levels, places, expansion, and Tab stop at each step, and each member’s muted line as
drawn: its place in its stack before its number, “3/3 · #8 · maintainer”.
`menu` is the page’s stack menu, mounted over a stand-in for the DOM: its heading is the
stack’s label on the shared label classes, and its members are the group’s, in one
order. Every step holds the session’s invariants: each listed pull request is drawn once
or held by its closed stack, a stack’s members are in the menu’s order, and the rest
keep the list’s.

```console
$ node tests/dom/github-pulls-stack-groups-session.js
{
  "steps": [
    {
      "step": "the list arrives before any stacks: flat",
      "grouped": false,
      "rows": [
        "#106",
        "#105",
        "#104",
        "…",
        "#5"
      ]
    },
    {
      "step": "stacks absent: flat",
      "grouped": false,
      "rows": [
        "#106",
        "#105",
        "#104",
        "…",
        "#5"
      ]
    },
    {
      "step": "stacks missing: flat",
      "grouped": false,
      "rows": [
        "#106",
        "#105",
        "#104",
        "…",
        "#5"
      ]
    },
    {
      "step": "stacks known: Stack #286 first, open, top of the stack first",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "tabStop": -286
    },
    {
      "step": "J walks into the stack and out past it, K steps back; only pulls open",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "marks": [
        "focus #8",
        "focus #7",
        "focus #6",
        "focus #106",
        "focus #6"
      ],
      "opened": [
        8,
        7,
        6,
        106,
        6
      ],
      "read ahead after the last open": [
        7,
        106,
        8,
        105
      ]
    },
    {
      "step": "Left on a pull request in a stack goes to the stack's row",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "marks": [
        "focus Stack #286"
      ]
    },
    {
      "step": "Left on the stack's row closes it",
      "grouped": true,
      "rows": [
        "▸ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ]
    },
    {
      "step": "J from a closed stack goes past it, and K comes back to it",
      "grouped": true,
      "rows": [
        "▸ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "marks": [
        "focus #106",
        "focus Stack #286"
      ],
      "opened": [
        106
      ]
    },
    {
      "step": "Right opens it",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ]
    },
    {
      "step": "Right again goes to its first pull request, which opens",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "marks": [
        "focus #8"
      ],
      "opened": [
        8
      ]
    },
    {
      "step": "Enter on the stack's row closes it",
      "grouped": true,
      "rows": [
        "▸ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "marks": [
        "focus Stack #286"
      ],
      "closed": [
        286
      ]
    },
    {
      "step": "an address that names #7 opens the stack that holds it",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ],
      "closed": [],
      "tabStop": 7
    },
    {
      "step": "Open: #8 is closed, so Stack #286 holds 2 of its 3",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (2 of 3) [1/99] · Stack #286, 3 pull requests, 2 in this list",
        "    #7 2/3 [1/2]",
        "    #6 1/3 [2/2]",
        "#106 [2/99]",
        "#105 [3/99]",
        "…",
        "#5 [99/99]"
      ]
    },
    {
      "step": "#8 in two stacks: once, under the first listed, its badge naming the other",
      "grouped": true,
      "rows": [
        "▾ Stack #290 (3) [1/99] · Stack #290, 3 pull requests",
        "    #10 3/3 [1/3]",
        "    #9 2/3 [2/3]",
        "    #8 1/3 · ⧉286 3/3 [3/3]",
        "▾ Stack #286 (3) [2/99] · Stack #286, 3 pull requests, 1 under Stack #290",
        "    #7 2/3 [1/2]",
        "    #6 1/3 [2/2]",
        "#106 [3/99]",
        "#105 [4/99]",
        "…",
        "#5 [99/99]"
      ]
    },
    {
      "step": "Closed: #286's one listed pull request sits under #290, so #286 has no row",
      "grouped": true,
      "rows": [
        "▾ Stack #290 (2 of 3) [1/1] · Stack #290, 3 pull requests, 2 in this list",
        "    #9 2/3 [1/2]",
        "    #8 1/3 · ⧉286 3/3 [2/2]"
      ]
    },
    {
      "step": "a failed refresh keeps the snapshot, which still groups",
      "grouped": true,
      "rows": [
        "▾ Stack #286 (3) [1/100] · Stack #286, 3 pull requests",
        "    #8 3/3 [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#106 [2/100]",
        "#105 [3/100]",
        "…",
        "#5 [100/100]"
      ]
    },
    {
      "step": "a repository with no stacks: flat",
      "grouped": false,
      "rows": [
        "#106",
        "#105",
        "#104",
        "…",
        "#5"
      ]
    },
    {
      "step": "stacks read for another account: flat",
      "grouped": false,
      "rows": [
        "#106",
        "#105",
        "#104",
        "…",
        "#5"
      ]
    }
  ],
  "mounted": {
    "member lines": [
      "#8: 3/3 · #8 · maintainer",
      "#7: 2/3 · #7 · forker",
      "#6: 1/3 · #6 · contributor"
    ],
    "files": {
      "Right on #8": "true",
      "then Left": "false"
    },
    "label": {
      "text": "Stack #286",
      "classes": "group-heading github-pull-stack-label"
    },
    "steps": [
      {
        "step": "mounted: Stack #286 open, its pull requests a level in",
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true · Tab stop",
          "#8 · treeitem · level 2 · 1/3 · expanded false",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "Space on the stack's row (the handle's toggleStack) closes it",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "and again opens it",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true · Tab stop",
          "#8 · treeitem · level 2 · 1/3 · expanded false",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "Right on the stack's row goes to its first pull request, which opens",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true",
          "#8 · treeitem · level 2 · 1/3 · expanded false · Tab stop",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ],
        "opened": [
          8
        ]
      },
      {
        "step": "Right on that pull request opens its files",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true",
          "#8 · treeitem · level 2 · 1/3 · expanded true · Tab stop",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "Left first closes its files, keeping the pull request",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true",
          "#8 · treeitem · level 2 · 1/3 · expanded false · Tab stop",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "Left again goes to the stack's row",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true · Tab stop",
          "#8 · treeitem · level 2 · 1/3 · expanded false",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "Left on the stack's row closes it",
        "handled": true,
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      },
      {
        "step": "a press on the stack's row opens it",
        "tree": [
          "Stack #286 · treeitem · level 1 · 1/100 · expanded true · Tab stop",
          "#8 · treeitem · level 2 · 1/3 · expanded false",
          "#7 · treeitem · level 2 · 2/3 · expanded false",
          "#6 · treeitem · level 2 · 3/3 · expanded false",
          "#106 · treeitem · level 1 · 2/100 · expanded false"
        ]
      }
    ]
  },
  "menu": {
    "heading": "Stack #290",
    "headingClasses": "group-heading github-pull-stack-label",
    "trigger": "Navigate Stack #290, position 2 of 3",
    "triggerTip": "Stack #290, position 2 of 3",
    "members": [
      10,
      9,
      8
    ],
    "groupRow": {
      "label": "Stack #290",
      "members": [
        10,
        9,
        8
      ]
    }
  },
  "invariants": true
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
