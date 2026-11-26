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

Each stack with a pull request in the list has a row, and under it, one level in, its
Whole stack row, which opens the stack’s own page, and then the stack’s pull requests in
the list, top of the stack first, as the pull request page’s stack menu lists them.
The Whole stack row is one of the stack’s rows, so their places count it: “1/4” under a
stack of three. No pull request is ever under the Whole stack row.
A stack’s row shows the stack’s size, “Stack #286 · 3 pulls”, the count its accessible
name says first, and the age of the newest update among its pull requests the list
holds.
The stacks come in the order of their first pull request in the list, and the pull
requests in no stack follow them, in the list’s order.
A pull request in two stacks sits once, under the first, and its badge names the other
by the Layers glyph, written ⧉ here, before its number; the other stack’s row’s
accessible name still counts it and says where it sits.
Until stacks are known for the list’s own GitHub account, and while none of the list’s
pull requests is in one, the list stays flat; there is no option.
The keys are a tree’s. A stack’s row is a row of the tree, as a folder is: J and K stop
on it and open nothing, Enter opens or closes it, Right opens it or goes to its first
row, Whole stack, and Left closes it, or from a row in it goes to it.
The Whole stack row opens the stack’s page as a pull request’s row opens its own, on J,
K, and Enter, and so does Right from the stack’s row.
A pull request’s row, its run and last line one item (mb-1z7j), is a folder too: Right
opens its changed files, and Left closes them before it goes up.
The Whole stack row is a folder in the same way, of the stack’s changed files, the
combined ones its page’s Diff summary lists: its change line and the chevron after it
are their toggle, as a pull request’s row’s last line is its own, and Space, Right, and
Left on the row open and close them (mb-odt4). An address that names a pull request in a
stack the reader closed opens the stack over it, and does so too when the list must
first move to a filter that holds the pull request, as from Open to All for a closed
one; one that names the stack’s page opens the stack and marks its Whole stack row.
A stack the reader closed over the open pull request stays closed when the tab is hidden
and shown again, on a landing that keeps the list’s place, and when a filter is picked:
only an address that names the pull request again opens it.
Home, the folder’s name or `0`, puts the list back as a fresh load draws it, from the
rows it holds and with no request: every stack open, no changed files open, a pull
request’s or a stack’s, and the Tab stop on the first row.

Each step’s `rows` are what a reader sees: a stack’s row with its label, its size, the
time its age tells, its place, and its accessible name; its Whole stack row and its pull
requests a level in with their places; and then the ends of the rest.
After a walk, `read ahead after the last open` is what the open asks to read next: its
neighbours as drawn, a stack’s row passed over, then the first pull requests drawn.
`mounted` mounts the panel over a stand-in for the DOM and drives its handle, as Space,
Right, and Left reach it, and a press on a stack’s row, on a Whole stack row, and on
that row’s change line and its chevron, which open and close the stack’s changed files
and open no page, printing the tree’s roles, levels, places, expansion, and Tab stop at
each step, with each row’s toggle under it; `the stack's files`, the Whole stack row’s
`aria-expanded` after Right and after Left, and what opening them first reads, the stack
alone, as its page reads it; `heading`, the stack’s row as first drawn, its text, its
age, and its accessible name; the Whole stack row’s name; and each member’s title line
as drawn: its title, then the stack menu’s muted dot and its place in its stack, and the
number, “Say more in the guide · 3/3 · #8”, where a pull request in no stack has no
place (mb-vkhd). `menu` is the page’s stack menu, mounted over a stand-in for the DOM:
its heading is the stack’s label on the shared label classes, its trigger shows its bare
position, a press opens it with focus on the current member, and its members are the
group’s, in one order.
`lines` is each member’s one line as drawn: its state icon’s state, as the list said it,
then its title, and at the line’s end its bold place, a muted dot, and its number, the
order a Pulls row has (mb-1kzu); `layout` is the parts that line is made of, one for
every member, the current one too.
`named` is #8’s two chips, one for each of its stacks, each naming its stack before its
position, as its page draws them.
Every step holds the session’s invariants: each listed pull request is drawn once, or
held by its closed stack; a stack’s members are in the menu’s order; the rows under an
open stack are its Whole stack row and its pull requests, one level in, each placed in
the one set they make; a stack’s time is the newest of its listed pull requests’; its
accessible name starts with the count its heading shows; and the rest keep the list’s
order.

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
        "#7"
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
        "#7"
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
        "#7"
      ]
    },
    {
      "step": "stacks known: Stack #286 among the pull requests, top of the stack first",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "tabStop": 106
    },
    {
      "step": "J walks into the stack, onto its Whole stack row first, which opens the stack's page, then its pull requests and out, and K steps back; the stack's row opens nothing",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus Whole stack of #286",
        "focus #8",
        "focus #7",
        "focus #6",
        "focus #5",
        "focus #6"
      ],
      "opened": [
        "Stack #286's page",
        8,
        7,
        6,
        5,
        6
      ],
      "read ahead after the last open": [
        7,
        5,
        106,
        105,
        104,
        103,
        102
      ]
    },
    {
      "step": "Left on a pull request in a stack goes to the stack's row",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus Stack #286"
      ]
    },
    {
      "step": "Left on the stack's row closes it",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▸ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ]
    },
    {
      "step": "J from a closed stack goes past it, and K comes back to it",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▸ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus #5",
        "focus Stack #286"
      ],
      "opened": [
        5
      ]
    },
    {
      "step": "Right opens it",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ]
    },
    {
      "step": "Right again goes to its first row, Whole stack, which opens the stack's page",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus Whole stack of #286"
      ],
      "opened": [
        "Stack #286's page"
      ]
    },
    {
      "step": "Enter on the stack's row closes it",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▸ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
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
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "closed": [],
      "tabStop": 7
    },
    {
      "step": "the reader closes the stack; an address that names its page opens it and marks its Whole stack row",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus Stack #286"
      ],
      "closed": [],
      "current": "Whole stack of #286",
      "tabStop": "Whole stack of #286"
    },
    {
      "step": "Left on the Whole stack row goes to its stack's row",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus Stack #286"
      ],
      "tabStop": "Stack #286"
    },
    {
      "step": "Right on the Whole stack row does nothing; Enter opens the stack's page",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "opened": [
        "Stack #286's page"
      ],
      "current": "Whole stack of #286"
    },
    {
      "step": "an address that names #7 again takes the mark back",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "current": "#7"
    },
    {
      "step": "the reader closes the stack and walks past it",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▸ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "marks": [
        "focus Stack #286",
        "focus #5"
      ],
      "opened": [
        5
      ],
      "closed": [
        286
      ],
      "tabStop": 5
    },
    {
      "step": "Home: every stack open, and the Tab stop on the first row",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "closed": [],
      "tabStop": 106,
      "requests": 0
    },
    {
      "step": "Open: #8 is closed, so Stack #286 holds 2 of its 3",
      "grouped": true,
      "rows": [
        "#106 [1/99]",
        "#105 [2/99]",
        "…",
        "#11 [96/99]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/99] · Stack #286, 3 pull requests, 2 in this list",
        "    Whole stack [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#5 [98/99]",
        "#10 [99/99]"
      ]
    },
    {
      "step": "#8 in two stacks: once, under the most recently updated stack, its badge naming the other",
      "grouped": true,
      "rows": [
        "▾ Stack #290 · 3 pulls · updated 2026-09-17T12:20:05Z [1/99] · Stack #290, 3 pull requests",
        "    Whole stack [1/4]",
        "    #10 3/3 [2/4]",
        "    #9 2/3 [3/4]",
        "    #8 1/3 · ⧉286 3/3 [4/4]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T12:20:04Z [2/99] · Stack #286, 3 pull requests, 1 under Stack #290",
        "    Whole stack [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
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
        "▾ Stack #290 · 3 pulls · updated 2026-09-17T12:20:05Z [1/1] · Stack #290, 3 pull requests, 2 in this list",
        "    Whole stack [1/3]",
        "    #9 2/3 [2/3]",
        "    #8 1/3 · ⧉286 3/3 [3/3]"
      ]
    },
    {
      "step": "a failed refresh keeps the snapshot, which still groups",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
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
        "#7"
      ]
    },
    {
      "step": "an address of Stack #286's page before the stacks are known: its row is revealed when they draw it",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "revealed while flat": [],
      "revealed once grouped": [
        "Whole stack of #286"
      ],
      "current": "Whole stack of #286",
      "tabStop": "Whole stack of #286"
    },
    {
      "step": "stacks read again: the row is not revealed again",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "revealed": []
    },
    {
      "step": "stacks read for another account: flat",
      "grouped": false,
      "rows": [
        "#106",
        "#105",
        "#104",
        "…",
        "#7"
      ]
    }
  ],
  "mounted": {
    "member lines": [
      "#8: Say more in the guide · 3/3 · #8",
      "#7: Count to two in the app · 2/3 · #7",
      "#6: Work item 6 · 1/3 · #6"
    ],
    "a pull request in no stack": "#106: Work item 106 · #106",
    "files": {
      "Right on #8": "false",
      "then Left": "false"
    },
    "the stack's files": {
      "Right on the Whole stack row": "false",
      "then Left": "false",
      "requests when first opened": [
        "/api/plugin/github/pull-files?number=106&offset=0"
      ]
    },
    "label": {
      "text": "Stack #286",
      "classes": "group-heading github-pull-stack-label"
    },
    "heading": {
      "text": "Stack #286 · 3 pulls",
      "age": "1m",
      "name": "Stack #286, 3 pull requests · 1m"
    },
    "Whole stack row": {
      "name": "Whole stack, Stack #286"
    },
    "steps": [
      {
        "step": "mounted: Stack #286 open, its Whole stack row and its pull requests one level in",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Space on the stack's row (the handle's toggleStack) closes it",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "and again opens it",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Right on the stack's row goes to its first row, Whole stack, which opens the stack's page",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded true · Tab stop",
          "  #106's toggle · hidden · chevron expanded"
        ]
      },
      {
        "step": "Right on the Whole stack row opens the stack's changed files, as on a pull request's row",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded true · Tab stop",
          "  #106's toggle · hidden · chevron expanded"
        ]
      },
      {
        "step": "Left first closes them, keeping the Whole stack row",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "J goes to its first pull request, which opens",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ],
        "opened": [
          105
        ]
      },
      {
        "step": "Right on that pull request opens its files, as on a folder's",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Left first closes its files, keeping the pull request",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Left again goes to the stack's row",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Left on the stack's row closes it",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "a press on the stack's row opens it",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Right, Right, J, Right: the Whole stack row, the stack's files, then #8, then #8's files",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ],
        "opened": [
          104
        ]
      },
      {
        "step": "K back to the Whole stack row, J down the stack, then Space on its row closes it",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ],
        "opened": [
          102
        ]
      },
      {
        "step": "Home: every stack open, no files open, the Tab stop on the first row",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Space on the Whole stack row (the handle's toggleStackFiles) opens the stack's changed files",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false · Tab stop",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "a press on its change line closes them, and opens no page",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "a press on the chevron after it opens them, and opens no page",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Left on the Whole stack row closes them",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "a press on the Whole stack row opens the stack's page",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ],
        "opened": [
          "Stack #286's page"
        ]
      },
      {
        "step": "the stack's page is open: its Whole stack row is the current row",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "Left on it goes to the stack's row",
        "handled": true,
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      },
      {
        "step": "an address that names #8 takes the mark back",
        "tree": [
          "#106 · treeitem · level 1 · 1/100 · expanded false",
          "  #106's toggle · hidden · chevron collapsed"
        ]
      }
    ]
  },
  "menu": {
    "heading": "Stack #290",
    "headingClasses": "group-heading github-pull-stack-label",
    "trigger": "Navigate Stack #290, position 2 of 3",
    "triggerText": "2/3",
    "triggerTip": "Stack #290, position 2 of 3",
    "focusOnOpen": {
      "member": 9,
      "current": true
    },
    "members": [
      10,
      9,
      8
    ],
    "lines": [
      "draft Stack change 10 3/3 · #10",
      "closed Stack change 9 2/3 · #9",
      "merged Stack change 8 1/3 · #8"
    ],
    "layout": [
      "github-pull-state-icon",
      "github-pull-stack-member-copy",
      "github-pull-stack-member-title",
      "github-pull-stack-member-position",
      "github-pull-stack-dot",
      "github-pull-stack-member-number",
      "github-pull-stack-member-by"
    ],
    "groupRow": {
      "label": "Stack #290",
      "members": [
        10,
        9,
        8
      ]
    },
    "named": [
      {
        "triggerText": "286 3/3",
        "trigger": "Navigate Stack #286, position 3 of 3"
      },
      {
        "triggerText": "290 1/3",
        "trigger": "Navigate Stack #290, position 1 of 3"
      }
    ]
  },
  "invariants": true
}
? 0
```

The session’s second part is what a reveal unfolds and what stays folded.
It prints on its own because one transcript of both parts was larger than tryscript can
match.
An address that names #8, which Open leaves out, moves the list to All and reveals
it there, opening Stack #286, which the reader closed, over it.
With #7 open and its stack closed over it, the tab hidden and shown again, a landing on
#6 that keeps the list’s place, and the Open filter picked each leave the stack closed,
and an address that names #7 again opens it.

```console
$ node tests/dom/github-pulls-stack-groups-session.js reveal
{
  "steps": [
    {
      "step": "on Open the reader closes Stack #286; an address that names #8, which Open leaves out, moves the list to All and reveals it there",
      "grouped": true,
      "rows": [
        "#106 [1/100]",
        "#105 [2/100]",
        "…",
        "#11 [96/100]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/100] · Stack #286, 3 pull requests",
        "    Whole stack [1/4]",
        "    #8 3/3 [2/4]",
        "    #7 2/3 [3/4]",
        "    #6 1/3 [4/4]",
        "#5 [98/100]",
        "#10 [99/100]",
        "#9 [100/100]"
      ],
      "filter": "open → all",
      "closed": "[286] → []",
      "revealed": [
        "#8"
      ],
      "current": "#8",
      "tabStop": "#8"
    },
    {
      "step": "the reader closes Stack #286 over the open pull request, #7: the tab shown again, a landing that keeps the list's place, and a filter picked leave it folded, and an address that names #7 again opens the stack",
      "grouped": true,
      "rows": [
        "#106 [1/99]",
        "#105 [2/99]",
        "…",
        "#11 [96/99]",
        "▾ Stack #286 · 3 pulls · updated 2026-09-17T08:08:00Z [97/99] · Stack #286, 3 pull requests, 2 in this list",
        "    Whole stack [1/3]",
        "    #7 2/3 [2/3]",
        "    #6 1/3 [3/3]",
        "#5 [98/99]",
        "#10 [99/99]"
      ],
      "folded": "all · closed [286]",
      "the tab hidden and shown again": "all · closed [286]",
      "a landing on #6 that keeps the list's place": "all · closed [286]",
      "the Open filter picked": "open · closed [286]",
      "an address that names #7 again": "open · closed []",
      "tabStop": "#7"
    }
  ],
  "invariants": true
}
? 0
```

## Test: stacks and standalone pull requests sort by activity in every filter

The controller runs over a partial window in each filter.
An update to a member outside the window moves its stack above the newer standalone PRs.

```console
$ node tests/dom/github-pulls-stack-groups-session.js recency
{
  "open": {
    "initial": [
      "#5",
      "Stack #286",
      "#99",
      "Stack #287",
      "#101"
    ],
    "after the closed member is updated": [
      "Stack #287",
      "#5",
      "Stack #286",
      "#99",
      "#101"
    ]
  },
  "closed": {
    "initial": [
      "#6",
      "Stack #286",
      "#98",
      "Stack #287",
      "#102"
    ],
    "after the closed member is updated": [
      "Stack #287",
      "#6",
      "Stack #286",
      "#98",
      "#102"
    ]
  },
  "all": {
    "initial": [
      "#6",
      "#5",
      "Stack #286",
      "#99",
      "#98",
      "Stack #287",
      "#102",
      "#101"
    ],
    "after the closed member is updated": [
      "Stack #287",
      "#6",
      "#5",
      "Stack #286",
      "#99",
      "#98",
      "#102",
      "#101"
    ]
  },
  "overlapping stacks in a partial Open window": [
    {
      "stack": 286,
      "members": [
        14
      ]
    },
    {
      "stack": 287,
      "members": [
        15
      ]
    }
  ],
  "partial Open window updates before the stack snapshot": [
    {
      "stack": 287,
      "members": [
        15
      ]
    },
    {
      "stack": 286,
      "members": [
        14
      ]
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
