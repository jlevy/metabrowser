---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Kind

The shell learns whether it shows an attached folder or an immutable Git pin from one
inline block the server writes into every page.
This browserless session runs that block and the `/api/tree?depth=2` payload exactly as
the in-process application served them for a folder and for a pin of the same names,
recorded in `tests/fixtures/source-kind-shell.json` and checked against the live
application by `tests/test_source_kind_session.py`. It then loads the production
navigation, plugin SDK, and filter modules and the shell’s source-kind gates.

The transcript pins what `metabrowser.sourceKind()` reports, each row’s rendered name
and displayed location, and which of Recent, index polling, the live event stream, and
the recency and ignore filters a pin turns off.
Row order is the server’s: a folder lists directories first, while a pin currently lists
its SPA tree in byte order of the names.

```console
$ node tests/dom/source-kind-session.js
[
  {
    "sourceKind": "filesystem",
    "shell": [
      "window.METABROWSER_SOURCE_KIND=\"filesystem\";",
      "window.METABROWSER_REPOSITORY_CONTEXT=null;"
    ],
    "rows": [
      {
        "path": "docs",
        "name": "docs",
        "row": "docs",
        "location": "docs"
      },
      {
        "path": "docs/guide.md",
        "name": "guide.md",
        "row": "guide.md",
        "location": "docs/guide.md"
      },
      {
        "path": "g1-data",
        "name": "g1-data",
        "row": "g1-data",
        "location": "g1-data"
      },
      {
        "path": "g1-data/note.txt",
        "name": "note.txt",
        "row": "note.txt",
        "location": "g1-data/note.txt"
      },
      {
        "path": "50%25-off.md",
        "name": "50%25-off.md",
        "row": "50%-off.md",
        "location": "50%-off.md"
      },
      {
        "path": "README.md",
        "name": "README.md",
        "row": "README.md",
        "location": "README.md"
      }
    ],
    "gates": {
      "filesPanelUsesRecentSource": true,
      "indexProgress": {
        "refreshes": 1,
        "intervals": [
          1000
        ]
      },
      "inventoryEvents": {
        "eventSourcesOpened": 1,
        "catalogFeedStarts": 0,
        "catalogFeedCanStart": false
      },
      "navFilterControls": [
        "recency",
        "types",
        "drawer",
        "size",
        "showIgnored"
      ]
    }
  },
  {
    "sourceKind": "git_revision",
    "shell": [
      "window.METABROWSER_SOURCE_KIND=\"git_revision\";",
      "window.METABROWSER_REPOSITORY_CONTEXT=null;"
    ],
    "rows": [
      {
        "path": "g1-ZG9jcw",
        "name": "docs",
        "row": "docs",
        "location": "docs"
      },
      {
        "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ",
        "name": "guide.md",
        "row": "guide.md",
        "location": "docs/guide.md"
      },
      {
        "path": "g1-ZzEtZGF0YQ",
        "name": "g1-data",
        "row": "g1-data",
        "location": "g1-data"
      },
      {
        "path": "g1-ZzEtZGF0YQ/g1-bm90ZS50eHQ",
        "name": "note.txt",
        "row": "note.txt",
        "location": "g1-data/note.txt"
      },
      {
        "path": "g1-NTAlLW9mZi5tZA",
        "name": "50%-off.md",
        "row": "50%-off.md",
        "location": "50%-off.md"
      },
      {
        "path": "g1-UkVBRE1FLm1k",
        "name": "README.md",
        "row": "README.md",
        "location": "README.md"
      }
    ],
    "gates": {
      "filesPanelUsesRecentSource": false,
      "indexProgress": {
        "refreshes": 0,
        "intervals": []
      },
      "inventoryEvents": {
        "eventSourcesOpened": 0,
        "catalogFeedStarts": 1,
        "catalogFeedCanStart": true
      },
      "navFilterControls": [
        "types",
        "drawer",
        "size"
      ]
    }
  }
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
