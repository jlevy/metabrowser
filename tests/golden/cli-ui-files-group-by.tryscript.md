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
The answer it paints is `tests/golden/cli-api-tree-groups.tryscript.md`’s first one.

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
