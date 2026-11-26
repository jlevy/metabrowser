---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the Files tab’s Group by, browserless

This session runs the production filter state and tree filter model from a command line.
It pins which request each Group by and filter choice makes, how the server’s grouped
answer becomes sections in its order, how a folder inside a section opens under that
section’s group, which filters Clear and the chevron’s name each count (both count Show
ignored turned off, which sits in the drawer beside the filters), that Clear resets Show
ignored and keeps the grouping, which band a file’s age falls in, and that a malformed
answer is refused. It also pins the shell’s Group by decisions, held in the model: each
section’s share of the first paint’s rows, the order a revealed row is looked for in,
the reopen plan after a refresh, which grouping a pressed row asks for ahead, the
prefetch’s keep, drop, abort, and take, how a file change makes its answers stale
without dropping them or restarting one still on its way, that the keyboard asks only
for a row it rests on (a row passed over asks for nothing, and the next key, a choice,
or the menu closing cancels the wait), which loads wait for first sections on their way
and what the wait says, and the loads’ lifecycle: a refresh during a first load runs
once after it, a newer choice aborts the load and its answer never paints, a stale
prefetch paints and then refreshes once, and the wait for first sections ends on a
paint, a failure, or a cancel.
The answer it paints is read from `tests/golden/cli-api-tree-groups.tryscript.md`, its
first one.

```console
$ node tests/dom/files-group-by-session.js
{
  "steps": [
    {
      "chose": "By file type",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&depth=2",
      "activeFilters": 0,
      "drawerFilters": 0
    },
    {
      "chose": "types .md and .py",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&types=.md%2C.py&depth=2",
      "activeFilters": 1,
      "drawerFilters": 1
    },
    {
      "chose": "Modified within Past hour",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&types=.md%2C.py&recency=1h&depth=2",
      "activeFilters": 2,
      "drawerFilters": 2
    },
    {
      "chose": "Show ignored off",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&types=.md%2C.py&include_ignored=0&recency=1h&depth=2",
      "activeFilters": 3,
      "drawerFilters": 3
    },
    {
      "chose": "Clear",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&depth=2",
      "activeFilters": 0,
      "drawerFilters": 0
    },
    {
      "chose": "By age",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=age&depth=2",
      "activeFilters": 0,
      "drawerFilters": 0
    },
    {
      "chose": "No grouping",
      "source": "recent",
      "action": "load-recent",
      "request": "/api/recent?window=24h&limit=5000",
      "activeFilters": 1,
      "drawerFilters": 1
    },
    {
      "chose": "Any age",
      "source": "tree",
      "action": "load-tree",
      "request": "/api/tree",
      "activeFilters": 0,
      "drawerFilters": 0
    }
  ],
  "sections": [
    {
      "key": "type:docs",
      "label": "Documentation",
      "icon": "doc",
      "files": 3,
      "topLevel": [
        "docs",
        "README.md",
        "notes.txt"
      ]
    },
    {
      "key": "type:code",
      "label": "Code",
      "icon": "alignLeft",
      "files": 3,
      "topLevel": [
        "src",
        "Makefile"
      ]
    },
    {
      "key": "type:data",
      "label": "Data",
      "icon": "list",
      "files": 1,
      "topLevel": [
        "data"
      ]
    },
    {
      "key": "type:other",
      "label": "Other",
      "icon": "file",
      "files": 2,
      "topLevel": [
        "logs",
        "misc"
      ]
    }
  ],
  "openFolder": {
    "code": "/api/tree?path=src&group=type%3Acode&depth=2",
    "other": "/api/tree?path=logs&group=type%3Aother&depth=2"
  },
  "ageBands": {
    "30": "live",
    "90": "live",
    "91": "1h",
    "3600": "1h",
    "3601": "24h",
    "259200": "7d",
    "3456000": "older"
  },
  "rowShares": {
    "30 rows, 4 sections": 7,
    "5 rows, 10 sections": 1,
    "0 sections": 30
  },
  "reveal": {
    "a Markdown file": [
      "type:docs",
      "type:code",
      "type:other"
    ],
    "a folder": [
      "type:docs",
      "type:code",
      "type:other"
    ],
    "a symlink": [
      "type:other",
      "type:docs",
      "type:code"
    ],
    "a file past Live's edge": [
      "age:1h",
      "age:live",
      "age:older"
    ],
    "a file with no mtime": [
      "age:live",
      "age:1h",
      "age:older"
    ]
  },
  "reopen": {
    "paintedOpen": [
      "src",
      "docs"
    ],
    "fetchFirst": [
      "src/app"
    ],
    "srcChildren": [
      "src/app",
      "src/lib"
    ]
  },
  "loads": {
    "a refresh, while the first sections are on their way": "after",
    "a refresh, while a refresh is on its way": "start",
    "another grouping, while the first sections are on their way": "start",
    "a refresh of another grouping": "start",
    "a choice, with nothing on its way": "start",
    "a refresh, with nothing on its way": "start"
  },
  "regroupingStatus": {
    "age": "Grouping by age…",
    "type": "Grouping by file type…"
  },
  "prefetchFor": {
    "No grouping, ungrouped": null,
    "By age, ungrouped": "/api/tree?group_by=age&depth=2",
    "By file type, grouped by type": null,
    "By age, grouped by type, under a filter": "/api/tree?group_by=age&types=.md&depth=2"
  },
  "prefetch": [
    {
      "step": "press By age",
      "started": [
        "age"
      ],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "press it again",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "press By file type",
      "started": [
        "type"
      ],
      "aborted": [],
      "kept": 2,
      "resting": false
    },
    {
      "step": "choose By age",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false,
      "took": true,
      "stale": false
    },
    {
      "step": "choose By age again",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false,
      "took": false
    },
    {
      "step": "press By file type after the TTL",
      "started": [
        "type"
      ],
      "aborted": [
        "type"
      ],
      "kept": 1,
      "resting": false
    },
    {
      "step": "a file changes",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "press By file type while its stale answer is on its way",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "choose By file type",
      "started": [],
      "aborted": [],
      "kept": 0,
      "resting": false,
      "took": true,
      "stale": true
    },
    {
      "step": "press By age, and its answer comes",
      "started": [
        "age"
      ],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "a file changes again",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "press By age again",
      "started": [
        "age"
      ],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "choose By age",
      "started": [],
      "aborted": [],
      "kept": 0,
      "resting": false,
      "took": true,
      "stale": false
    },
    {
      "step": "press By file type",
      "started": [
        "type"
      ],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "press By age under a .md filter",
      "started": [
        "age under .md"
      ],
      "aborted": [
        "type"
      ],
      "kept": 1,
      "resting": false
    }
  ],
  "keyboardPrefetch": [
    {
      "step": "↓ to By age",
      "started": [],
      "aborted": [],
      "kept": 0,
      "resting": true
    },
    {
      "step": "↓ to By file type before the dwell passes",
      "started": [],
      "aborted": [],
      "kept": 0,
      "resting": true
    },
    {
      "step": "the dwell passes",
      "started": [
        "type"
      ],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "↑ to By age",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": true
    },
    {
      "step": "Escape closes the menu",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "the dwell would have passed",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "↓ to By age, then ↓ to No grouping",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "the dwell passes on No grouping",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "↓ to By age",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": true
    },
    {
      "step": "Enter chooses it before the dwell passes",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false,
      "took": false
    },
    {
      "step": "the dwell would have passed",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "↓ to By age, and focus leaves the menu",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": true
    },
    {
      "step": "the dwell passes",
      "started": [],
      "aborted": [],
      "kept": 1,
      "resting": false
    },
    {
      "step": "↓ to By age, and the pointer presses it",
      "started": [
        "age"
      ],
      "aborted": [],
      "kept": 2,
      "resting": false
    }
  ],
  "groupedLoads": {
    "a refresh during a first load waits, then runs once": [
      "wait for type",
      "ask type",
      "a refresh: true",
      "another: true",
      "paint type",
      "wait ends",
      "refresh",
      "wait for type (refresh)",
      "ask type (refresh)",
      "paint type",
      "wait ends"
    ],
    "a newer choice aborts the load, and its answer never paints": [
      "wait for type",
      "ask type",
      "abort type",
      "wait ends",
      "wait for age",
      "ask age",
      "drop type",
      "paint age",
      "wait ends"
    ],
    "a stale prefetch paints, then refreshes once": [
      "wait for type",
      "ask type",
      "paint type",
      "wait ends",
      "refresh",
      "wait for type (refresh)",
      "ask type (refresh)",
      "paint type",
      "wait ends"
    ],
    "settled resolves on paint, on failure, and on cancel": [
      "wait for type",
      "ask type",
      "paint type",
      "wait ends",
      "settled (painted)",
      "wait for type",
      "ask type",
      "fail type",
      "wait ends",
      "settled (failed)",
      "wait for type",
      "ask type",
      "abort type",
      "wait ends",
      "settled (cancelled)",
      "drop type",
      "wait for type (refresh)",
      "ask type (refresh)",
      "settled (a refresh paints no new sections)",
      "paint type",
      "wait ends"
    ]
  },
  "uncounted": {
    "key": "type:docs",
    "id": "docs",
    "label": "Documentation",
    "icon": null,
    "files": null,
    "size": null,
    "tree": []
  },
  "refused": [
    "no grouping: a grouped tree answer names no grouping",
    "no groups: a grouped tree answer has no groups",
    "a group with no id: a group has no id or label"
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
