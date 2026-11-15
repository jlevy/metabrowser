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
section’s group, that Clear keeps the grouping, which band a file’s age falls in, and
that a malformed answer is refused.
It also pins the shell’s Group by decisions, held as pure functions: each section’s
share of the first paint’s rows, the order a revealed row is looked for in, the reopen
plan after a refresh, and the prefetch’s keep, abort, take, and clear.
The answer it paints is read from `tests/golden/cli-api-tree-groups.tryscript.md`, its
first one.

```console
$ node tests/dom/files-group-by-session.js
{
  "steps": [
    {
      "chose": "File type",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&depth=2",
      "activeFilters": 0
    },
    {
      "chose": "types .md and .py",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&types=.md%2C.py&depth=2",
      "activeFilters": 1
    },
    {
      "chose": "Modified within Past hour",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&types=.md%2C.py&recency=1h&depth=2",
      "activeFilters": 2
    },
    {
      "chose": "Clear",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=type&depth=2",
      "activeFilters": 0
    },
    {
      "chose": "Age",
      "source": "grouped",
      "action": "load-groups",
      "request": "/api/tree?group_by=age&depth=2",
      "activeFilters": 0
    },
    {
      "chose": "No grouping",
      "source": "recent",
      "action": "load-recent",
      "request": "/api/recent?window=24h&limit=5000",
      "activeFilters": 1
    },
    {
      "chose": "Any age",
      "source": "tree",
      "action": "load-tree",
      "request": "/api/tree",
      "activeFilters": 0
    }
  ],
  "sections": [
    {
      "key": "type:docs",
      "label": "Documentation",
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
      "files": 3,
      "topLevel": [
        "src",
        "Makefile"
      ]
    },
    {
      "key": "type:data",
      "label": "Data",
      "files": 1,
      "topLevel": [
        "data"
      ]
    },
    {
      "key": "type:other",
      "label": "Other",
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
  "prefetch": [
    {
      "step": "open the menu",
      "started": [
        "age",
        "type"
      ],
      "aborted": [],
      "kept": 2
    },
    {
      "step": "open it again",
      "started": [],
      "aborted": [],
      "kept": 2
    },
    {
      "step": "open it while grouped by type",
      "started": [],
      "aborted": [
        "type"
      ],
      "kept": 1
    },
    {
      "step": "choose Age",
      "started": [],
      "aborted": [],
      "kept": 0,
      "took": true
    },
    {
      "step": "choose Age again",
      "started": [],
      "aborted": [],
      "kept": 0,
      "took": false
    },
    {
      "step": "open the menu",
      "started": [
        "age",
        "type"
      ],
      "aborted": [],
      "kept": 2
    },
    {
      "step": "open it after the TTL",
      "started": [
        "age",
        "type"
      ],
      "aborted": [
        "age",
        "type"
      ],
      "kept": 2
    },
    {
      "step": "a file changes",
      "started": [],
      "aborted": [
        "age",
        "type"
      ],
      "kept": 0
    }
  ],
  "uncounted": {
    "key": "type:docs",
    "id": "docs",
    "label": "Documentation",
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
