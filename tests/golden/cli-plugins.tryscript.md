---
path:
  - ../fixtures/github-status
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_OPEN_IN: "browser"
patterns:
  BUILTIN: '\S+/builtin_plugins'
  FAKE_GH: '[^\s"]+/fixtures/github-status/gh'
---
# Golden tests: plugin modes

`--plugins`, `--plugin NAME`, and `--doctor` in text and JSON. The builtin plugin set is
stable; the absolute checkout prefix of each plugin’s `static_root` is elided with the
`[BUILTIN]` pattern.
`--doctor` also reports where `metab --present` opens a target, the `open_in`
preference, and the app it finds; this file sets `METABROWSER_OPEN_IN=browser`, which
looks for no app, so the report is the same on every machine.
`tests/golden/cli-present-browser.txt` shows what it finds with a stand-in app.
The setup checks that end the report depend on the host, so they are elided here
(`...`); `cli-doctor.tryscript.md` pins them with a stand-in Git.

## Test: --plugins lists every discovered plugin

```console
$ metab --plugins
NAME           SOURCE   KINDS                   REQUIRES        VIEWS  HOOKS
-------------  -------  ----------------------  --------------  -----  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
agents         builtin  agent-log,agent-thread  structured      8      charts,catalog,sessions,session,records,live
binary         builtin  -                       -               1      chunk
delimited      builtin  delimited               table           2      -
diff           builtin  diff                    structured,pdf  1      document,children,comparison
event-log      builtin  event-log               agents          5      timeline,slowest,kinds,errors
folder         builtin  -                       markdown        2      -
fsqlite        builtin  sqlite-store            sqlite,table    3      info,schema,children
github         builtin  -                       markdown,diff   3      pull,pull-refresh,pull-cores-prepare,pull-comparison,pull-image,pull-rendered-diff,pull-size,pull-timeline,pull-markdown,guided-review,pulls,pulls-refresh,stacks,stacks-refresh,stack-change,stack,stack-comparison,labels,labels-refresh,pull-files,pull-files-summary,pull-statuses,pull-files-refresh,pulls-prefetch,cache-clear,status
html           builtin  html                    -               2      -
image          builtin  -                       -               1      -
markdown       builtin  markdown,mermaid        pdf             4      -
pdf            builtin  pdf                     -               1      preview,preview-image
sqlite         builtin  sqlite                  table           3      info,schema,children
structured     builtin  structured              table           3      parsed
table          builtin  -                       -               0      tables,schema,rows,record,card
text           builtin  -                       -               1      -
unknown-jsonl  builtin  -                       agents          2      -
? 0
```

## Test: --plugins --json

```console
$ metab --plugins --json
{
  "plugins": [
    {
      "name": "agents",
      "display_name": "Agent Session Browser",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/agents",
      "kinds": [
        "agent-log",
        "agent-thread"
      ],
      "requires": [
        "structured"
      ],
      "python_requires": [
        "cachetools",
        "prettyfmt",
        "starlette"
      ],
      "views": [
        "agents",
        "agent-sessions",
        "session",
        "log",
        "charts",
        "raw",
        "session",
        "log"
      ],
      "view_count": 8,
      "data_hooks": [
        "charts",
        "catalog",
        "sessions",
        "session",
        "records",
        "live"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "binary",
      "display_name": "Binary",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/binary",
      "kinds": [],
      "requires": [],
      "python_requires": [
        "starlette"
      ],
      "views": [
        "bytes"
      ],
      "view_count": 1,
      "data_hooks": [
        "chunk"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "delimited",
      "display_name": "Delimited Text",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/delimited",
      "kinds": [
        "delimited"
      ],
      "requires": [
        "table"
      ],
      "python_requires": [],
      "views": [
        "table",
        "source"
      ],
      "view_count": 2,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "diff",
      "display_name": "Diff",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/diff",
      "kinds": [
        "diff"
      ],
      "requires": [
        "structured",
        "pdf"
      ],
      "python_requires": [
        "starlette"
      ],
      "views": [
        "diff"
      ],
      "view_count": 1,
      "data_hooks": [
        "document",
        "children",
        "comparison"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "event-log",
      "display_name": "Event log",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/event_log",
      "kinds": [
        "event-log"
      ],
      "requires": [
        "agents"
      ],
      "python_requires": [
        "starlette"
      ],
      "views": [
        "timeline",
        "latency",
        "kinds",
        "errors",
        "raw"
      ],
      "view_count": 5,
      "data_hooks": [
        "timeline",
        "slowest",
        "kinds",
        "errors"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "folder",
      "display_name": "Folder",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/folder",
      "kinds": [],
      "requires": [
        "markdown"
      ],
      "python_requires": [],
      "views": [
        "overview",
        "treemap"
      ],
      "view_count": 2,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "fsqlite",
      "display_name": "fsqlite",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/fsqlite",
      "kinds": [
        "sqlite-store"
      ],
      "requires": [
        "sqlite",
        "table"
      ],
      "python_requires": [
        "starlette"
      ],
      "views": [
        "table",
        "schema",
        "info"
      ],
      "view_count": 3,
      "data_hooks": [
        "info",
        "schema",
        "children"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "github",
      "display_name": "GitHub",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/github",
      "kinds": [],
      "requires": [
        "markdown",
        "diff"
      ],
      "python_requires": [
        "markdown-it-py",
        "pydantic",
        "softschema",
        "starlette"
      ],
      "views": [
        "pull-request",
        "pull-stack",
        "pull-request-list"
      ],
      "view_count": 3,
      "data_hooks": [
        "pull",
        "pull-refresh",
        "pull-cores-prepare",
        "pull-comparison",
        "pull-image",
        "pull-rendered-diff",
        "pull-size",
        "pull-timeline",
        "pull-markdown",
        "guided-review",
        "pulls",
        "pulls-refresh",
        "stacks",
        "stacks-refresh",
        "stack-change",
        "stack",
        "stack-comparison",
        "labels",
        "labels-refresh",
        "pull-files",
        "pull-files-summary",
        "pull-statuses",
        "pull-files-refresh",
        "pulls-prefetch",
        "cache-clear",
        "status"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "html",
      "display_name": "HTML",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/html",
      "kinds": [
        "html"
      ],
      "requires": [],
      "python_requires": [],
      "views": [
        "preview",
        "source"
      ],
      "view_count": 2,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "image",
      "display_name": "Image",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/image",
      "kinds": [],
      "requires": [],
      "python_requires": [],
      "views": [
        "preview"
      ],
      "view_count": 1,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "markdown",
      "display_name": "Markdown",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/markdown",
      "kinds": [
        "markdown",
        "mermaid"
      ],
      "requires": [
        "pdf"
      ],
      "python_requires": [],
      "views": [
        "rendered",
        "source",
        "diagram",
        "source"
      ],
      "view_count": 4,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "pdf",
      "display_name": "PDF",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/pdf",
      "kinds": [
        "pdf"
      ],
      "requires": [],
      "python_requires": [
        "pypdfium2",
        "starlette"
      ],
      "views": [
        "preview"
      ],
      "view_count": 1,
      "data_hooks": [
        "preview",
        "preview-image"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "sqlite",
      "display_name": "SQLite",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/sqlite",
      "kinds": [
        "sqlite"
      ],
      "requires": [
        "table"
      ],
      "python_requires": [
        "starlette"
      ],
      "views": [
        "table",
        "schema",
        "info"
      ],
      "view_count": 3,
      "data_hooks": [
        "info",
        "schema",
        "children"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "structured",
      "display_name": "Structured Data",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/structured",
      "kinds": [
        "structured"
      ],
      "requires": [
        "table"
      ],
      "python_requires": [
        "cachetools",
        "json5",
        "pyyaml",
        "ruamel.yaml",
        "starlette"
      ],
      "views": [
        "tree",
        "table",
        "source"
      ],
      "view_count": 3,
      "data_hooks": [
        "parsed"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "table",
      "display_name": "Tables",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/table",
      "kinds": [],
      "requires": [],
      "python_requires": [
        "starlette"
      ],
      "views": [],
      "view_count": 0,
      "data_hooks": [
        "tables",
        "schema",
        "rows",
        "record",
        "card"
      ],
      "disabled_data_hooks": []
    },
    {
      "name": "text",
      "display_name": "Text",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/text",
      "kinds": [],
      "requires": [],
      "python_requires": [],
      "views": [
        "source"
      ],
      "view_count": 1,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "unknown-jsonl",
      "display_name": "Unknown JSONL",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/unknown_jsonl",
      "kinds": [],
      "requires": [
        "agents"
      ],
      "python_requires": [],
      "views": [
        "log",
        "raw"
      ],
      "view_count": 2,
      "data_hooks": [],
      "disabled_data_hooks": []
    }
  ],
  "errors": []
}
? 0
```

## Test: --plugin markdown shows one manifest

```console
$ metab --plugin markdown
name:            markdown
display_name:    Markdown
version:         0.0.1
sdk_version:     0.8
source:          builtin
static_root:     [BUILTIN]/markdown
requires:        pdf
python_requires: (none)

kinds:
  - id=markdown priority=0 match={'ext': '.md'}
  - id=mermaid priority=0 match={'exts': ['.mmd', '.mermaid']}

views:
  - markdown/rendered 'Document' (default, key V)
  - markdown/source 'Source' (key S)
  - mermaid/diagram 'Diagram' (default, key V)
  - mermaid/source 'Source' (key S)

data hooks:
  (none)

assets in static_root:
  - diagram-frame-entry.js
  - diagram-frame.css
  - diagram-frame.js
  - diagrams.js
  - dom-traversal.js
  - index.js
  - inert-render.js
  - inert-toc.js
  - link-enhancer.js
  - links.js
  - manifest.toml
  - markdown-worker-client.js
  - markdown-worker-operations.js
  - markdown-worker.js
  - markdown.css
  - mermaid-view.js
  - package.json
  - place-rendered.js
  - print-indicator.js
  - print-ready.js
  - project-adapters.js
  - reconciliation-coordinator.js
  - render-refusal.js
  - rendered.js
  - source.js
  - toc-toggle.js
  - transclusion.js
  - wiki-enhancer.js
  - wiki-parser.js
  - wiki-resolver.js
? 0
```

## Test: --plugin markdown --json

```console
$ metab --plugin markdown --json
{
  "plugin": {
    "name": "markdown",
    "display_name": "Markdown",
    "version": "0.0.1",
    "sdk_version": "0.8",
    "source": "builtin",
    "static_root": "[BUILTIN]/markdown",
    "requires": [
      "pdf"
    ],
    "python_requires": [],
    "kinds": [
      {
        "id": "markdown",
        "match": {
          "ext": ".md"
        },
        "priority": 0
      },
      {
        "id": "mermaid",
        "match": {
          "exts": [
            ".mmd",
            ".mermaid"
          ]
        },
        "priority": 0
      }
    ],
    "views": [
      {
        "kind": "markdown",
        "id": "rendered",
        "label": "Document",
        "key": "v",
        "default": true,
        "container_class": "content-body metabrowser-kpress-host md-body",
        "printable": true,
        "print_profile": "document",
        "render_runtime": "kpress"
      },
      {
        "kind": "markdown",
        "id": "source",
        "label": "Source",
        "key": "s",
        "default": false,
        "container_class": "content-body metabrowser-source-host",
        "printable": true,
        "print_profile": "source",
        "render_runtime": "client"
      },
      {
        "kind": "mermaid",
        "id": "diagram",
        "label": "Diagram",
        "key": "v",
        "default": true,
        "container_class": "content-body metabrowser-kpress-host md-body",
        "printable": false,
        "print_profile": "plain",
        "render_runtime": "kpress"
      },
      {
        "kind": "mermaid",
        "id": "source",
        "label": "Source",
        "key": "s",
        "default": false,
        "container_class": "content-body metabrowser-source-host",
        "printable": true,
        "print_profile": "source",
        "render_runtime": "client"
      }
    ],
    "data_hooks": [],
    "disabled_data_hooks": [],
    "table_sources": [],
    "assets": [
      "diagram-frame-entry.js",
      "diagram-frame.css",
      "diagram-frame.js",
      "diagrams.js",
      "dom-traversal.js",
      "index.js",
      "inert-render.js",
      "inert-toc.js",
      "link-enhancer.js",
      "links.js",
      "manifest.toml",
      "markdown-worker-client.js",
      "markdown-worker-operations.js",
      "markdown-worker.js",
      "markdown.css",
      "mermaid-view.js",
      "package.json",
      "place-rendered.js",
      "print-indicator.js",
      "print-ready.js",
      "project-adapters.js",
      "reconciliation-coordinator.js",
      "render-refusal.js",
      "rendered.js",
      "source.js",
      "toc-toggle.js",
      "transclusion.js",
      "wiki-enhancer.js",
      "wiki-parser.js",
      "wiki-resolver.js"
    ]
  },
  "errors": []
}
? 0
```

## Test: --doctor checks every plugin

tryscript matches stdout and stderr as one text, so each stream of a clean run is
recorded on its own: the answer is on stdout, and stderr is empty.

```console
$ metab --doctor 2>/dev/null
metab --doctor: open_in browser (environment); --present looks for no app
metab --doctor: 17 plugin(s) OK
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
...
? 0
```

## Test: --doctor writes nothing to stderr when nothing is wrong

```console
$ metab --doctor >/dev/null
? 0
```

## Test: --doctor --json

```console
$ metab --doctor --json 2>/dev/null
{
  "ok": true,
  "plugin_count": 17,
  "problems": [],
  "open_in": {
    "value": "browser",
    "source": "environment",
    "present_browser": true,
    "app": null
  },
  "github": {
    "host": "github.com",
    "state": "ok",
    "message": "GitHub CLI is signed in to github.com as octo-reader.",
    "fix": null,
    "remedy": null,
    "gh_path": "[FAKE_GH]",
    "gh_version": "2.98.0",
    "gh_minimum": "2.81.0",
    "account": "octo-reader",
    "token_source": "keyring",
    "scopes": [
      "gist",
      "read:org",
      "repo",
      "workflow"
    ]
  },
...
}
? 0
```

## Test: --doctor --json writes nothing to stderr when nothing is wrong

```console
$ metab --doctor --json >/dev/null
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
