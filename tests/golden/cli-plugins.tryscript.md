---
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
patterns:
  BUILTIN: '\S+/builtin_plugins'
---
# Golden tests: plugin modes

`--plugins`, `--plugin NAME`, and `--doctor` in text and JSON. The builtin plugin set is
stable; the absolute checkout prefix of each plugin’s `static_root` is elided with the
`[BUILTIN]` pattern.

## Test: --plugins lists every discovered plugin

```console
$ metab --plugins
NAME           SOURCE   KINDS       VIEWS  HOOKS
-------------  -------  ----------  -----  ----------------------------
agent-log      builtin  agent-log   3      charts
binary         builtin  -           1      chunk
diff           builtin  diff        1      document,children,comparison
folder         builtin  -           2      -
markdown       builtin  markdown    2      -
structured     builtin  structured  2      parsed
text           builtin  -           1      -
unknown-jsonl  builtin  -           2      -
? 0
```

## Test: --plugins --json

```console
$ metab --plugins --json
{
  "plugins": [
    {
      "name": "agent-log",
      "display_name": "Agent log (Claude / Gemini / Pi)",
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
      "name": "markdown",
      "display_name": "Markdown",
      "version": "0.0.1",
      "source": "builtin",
      "static_root": "[BUILTIN]/markdown",
      "kinds": [
        "markdown"
      ],
      "views": [
        "rendered",
        "source"
      ],
      "view_count": 2,
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
sdk_version:  0.3
source:       builtin
static_root:  [BUILTIN]/markdown

kinds:
  - id=markdown priority=0 match={'ext': '.md'}

views:
  - markdown/rendered 'Document' (default)
  - markdown/source 'Source'

data hooks:
  (none)

assets in static_root:
  - github_localizer.js
  - graph_analysis.js
  - index.js
  - link_enhancer.js
  - link_scanner.js
  - links.js
  - manifest.toml
  - markdown.css
  - project_adapters.js
  - rendered.js
  - source.js
  - transclusion.js
  - wiki_enhancer.js
  - wiki_parser.js
  - wiki_resolver.js
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
    "sdk_version": "0.3",
    "source": "builtin",
    "static_root": "[BUILTIN]/markdown",
    "kinds": [
      {
        "id": "markdown",
        "match": {
          "ext": ".md"
        },
        "priority": 0
      }
    ],
    "views": [
      {
        "kind": "markdown",
        "id": "rendered",
        "label": "Document",
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
      "github_localizer.js",
      "graph_analysis.js",
      "index.js",
      "link_enhancer.js",
      "link_scanner.js",
      "links.js",
      "manifest.toml",
      "markdown.css",
      "project_adapters.js",
      "rendered.js",
      "source.js",
      "transclusion.js",
      "wiki_enhancer.js",
      "wiki_parser.js",
      "wiki_resolver.js"
    ]
  },
  "errors": []
}
? 0
```

## Test: --doctor checks every plugin

```console
$ metab --doctor
metab --doctor: 8 plugin(s) OK
? 0
```

## Test: --doctor --json

```console
$ metab --doctor --json
{
  "ok": true,
  "plugin_count": 8,
  "problems": []
}
? 0
```
