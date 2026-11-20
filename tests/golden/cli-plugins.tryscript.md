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
NAME           SOURCE   KINDS             VIEWS  HOOKS
-------------  -------  ----------------  -----  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
agent-log      builtin  agent-log         3      charts
binary         builtin  -                 1      chunk
diff           builtin  diff              1      document,children,comparison
event-log      builtin  event-log         5      timeline,slowest,kinds,errors
folder         builtin  -                 2      -
github         builtin  -                 2      pull,pull-refresh,pull-cores-prepare,pull-comparison,pull-image,pull-rendered-diff,pull-timeline,pull-markdown,pulls,pulls-refresh,stacks,stacks-refresh,stack-change,labels,labels-refresh,pull-files,pull-files-summary,pull-files-refresh,pulls-prefetch,cache-clear,status
html           builtin  html              2      -
image          builtin  -                 1      -
markdown       builtin  markdown,mermaid  4      -
structured     builtin  structured        2      parsed
text           builtin  -                 1      -
unknown-jsonl  builtin  -                 2      -
? 0
```

## Test: --plugins --json

```console
$ metab --plugins --json
{
  "plugins": [
    {
      "name": "agent-log",
      "display_name": "Agent log (Claude / Codex / Gemini / Pi)",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/agent_log",
      "kinds": [
        "agent-log"
      ],
      "views": [
        "log",
        "charts",
        "raw"
      ],
      "view_count": 3,
      "data_hooks": [
        "charts"
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
      "name": "diff",
      "display_name": "Diff",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/diff",
      "kinds": [
        "diff"
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
      "views": [
        "overview",
        "treemap"
      ],
      "view_count": 2,
      "data_hooks": [],
      "disabled_data_hooks": []
    },
    {
      "name": "github",
      "display_name": "GitHub",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/github",
      "kinds": [],
      "views": [
        "pull-request",
        "pull-request-list"
      ],
      "view_count": 2,
      "data_hooks": [
        "pull",
        "pull-refresh",
        "pull-cores-prepare",
        "pull-comparison",
        "pull-image",
        "pull-rendered-diff",
        "pull-timeline",
        "pull-markdown",
        "pulls",
        "pulls-refresh",
        "stacks",
        "stacks-refresh",
        "stack-change",
        "labels",
        "labels-refresh",
        "pull-files",
        "pull-files-summary",
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
      "name": "structured",
      "display_name": "Structured Data",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/structured",
      "kinds": [
        "structured"
      ],
      "views": [
        "tree",
        "source"
      ],
      "view_count": 2,
      "data_hooks": [
        "parsed"
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
name:         markdown
display_name: Markdown
version:      0.0.1
sdk_version:  0.7
source:       builtin
static_root:  [BUILTIN]/markdown

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
  - github-localizer.js
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
    "sdk_version": "0.7",
    "source": "builtin",
    "static_root": "[BUILTIN]/markdown",
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
    "assets": [
      "diagram-frame-entry.js",
      "diagram-frame.css",
      "diagram-frame.js",
      "diagrams.js",
      "dom-traversal.js",
      "github-localizer.js",
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
metab --doctor: 12 plugin(s) OK
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
  "plugin_count": 12,
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
