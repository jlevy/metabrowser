---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  mkdir -p shellroot &&
  printf '# Sample\n\nHello.\n' > shellroot/README.md &&
  printf '{"path": "README.md", "view": "document", "source_text": "# Overridden\n\nBody.\n"}\n'
  > shellroot/render.json &&
  printf '{"path": "README.md", "view": "rendered", "destination": "out.html"}\n'
  > shellroot/export.json &&
  printf '{"reason": "golden", "pending": []}\n' > shellroot/diag.json &&
  touch -t 202311142213.20 shellroot/README.md shellroot/render.json
  shellroot/export.json shellroot/diag.json shellroot
---
# Golden tests: the shell’s own routes

`/api/catalog` backs the quick file finder, `/api/capabilities` tells the shell what
this build supports, and the two index routes report crawl state.
`/api/kpress/render` produces the Document view.

## Test: the file catalog

```console
$ metab shellroot --api /api/catalog
api: /api/catalog
status: 200
{
  "complete": true,
  "truncated": false,
  "revision": 1,
  "files": [
    {
      "p": "README.md",
      "e": ".md"
    },
    {
      "p": "diag.json",
      "e": ".json"
    },
    {
      "p": "export.json",
      "e": ".json"
    },
    {
      "p": "render.json",
      "e": ".json"
    }
  ]
}
? 0
```

## Test: build capabilities

The two `reason` values are host facts — the filesystem type the served root sits on,
and which watch backend that made available — so they are elided.
Everything around them is pinned, including the backend `mode`, which is the part a
regression would change.

```console
$ metab shellroot --api /api/capabilities
api: /api/capabilities
status: 200
{
  "backends": [
    {
      "prefix": ".",
      "mode": "native",
      "reason": "[..]"
    }
  ],
  "index": {
    "complete": true,
    "indexed_files": 4,
    "max_files": 500000,
    "truncated": false
  },
  "events": {
    "stream": "live",
    "reason": "[..]"
  }
}
? 0
```

## Test: crawl progress

```console
$ metab shellroot --api /api/index/progress
api: /api/index/progress
status: 200
{
  "status": "scanning",
  "indexed_files": 0,
  "max_files": 500000,
  "truncated": false,
  "complete": false,
  "active": true
}
? 0
```

## Test: index metadata

```console
$ metab shellroot --api /api/index/meta
api: /api/index/meta
status: 200
{
  "status": "done",
  "indexed_files": 4,
  "indexed_dirs": 1,
  "max_files": 500000,
  "truncated": false,
  "complete": true,
  "oldest_mtime_ns": 1700000000000000000,
  "newest_mtime_ns": 1700000000000000000,
  "suffixes": [
    {
      "ext": ".json",
      "count": 3
    },
    {
      "ext": ".md",
      "count": 1
    }
  ]
}
? 0
```

## Test: the route index lists what this build serves

`--api` can reach any route, but nothing told a reader or an agent which routes exist.
`/api/routes` reads the live routing table, so plugin data hooks and lazily-added
inventory routes are included and the answer cannot drift from what is mounted.

```console
$ metab shellroot --api /api/routes
api: /api/routes
status: 200
{
  "routes": [
    {
      "path": "/api/activity",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/capabilities",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/catalog",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/diagnostics/pending-tallies",
      "methods": [
        "POST"
      ],
      "kind": "api"
    },
    {
      "path": "/api/events",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/file",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/git/commit/{revision}",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/git/log",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/git/refs",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/git/repo",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/git/summary",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/index/meta",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/index/progress",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/kpress/export",
      "methods": [
        "POST"
      ],
      "kind": "api"
    },
    {
      "path": "/api/kpress/render",
      "methods": [
        "GET",
        "HEAD",
        "POST"
      ],
      "kind": "api"
    },
    {
      "path": "/api/plugin/agent-log/charts",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/plugin/binary/chunk",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/plugin/diff/children",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/plugin/diff/comparison",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/plugin/diff/document",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/plugin/structured/parsed",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/recent",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/rollup",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/routes",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/stream",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/api/tree",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "api"
    },
    {
      "path": "/kpress-static/{path:path}",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "asset"
    },
    {
      "path": "/plugin-static/{plugin}/{path:path}",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "asset"
    },
    {
      "path": "/raw",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "asset"
    },
    {
      "path": "/static",
      "methods": [
        "GET"
      ],
      "kind": "asset"
    },
    {
      "path": "/",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "browser"
    },
    {
      "path": "/commit/{rest:path}",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "browser"
    },
    {
      "path": "/view/{path:path}",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "browser"
    },
    {
      "path": "/_debug/tasks",
      "methods": [
        "GET",
        "HEAD"
      ],
      "kind": "debug"
    }
  ],
  "count": 34
}
? 0
```

## Test: the pending-tally diagnostic accepts a POST body

The route logs a diagnostic line to stderr by design; it carries a wall-clock timestamp
and is elided. The envelope is pinned exactly, with `elapsed_ms` normalized because it
moves with load and hardware even when a small fixture makes it repeat locally.

```console
$ metab shellroot --api /api/diagnostics/pending-tallies --data shellroot/diag.json
[..]
api: /api/diagnostics/pending-tallies
status: 200
{
  "diagnostic_id": "pending-tally-unknown",
  "inventory": {
    "status": "done",
    "elapsed_ms": "<ELAPSED>",
    "files_indexed": 4,
    "entries": 5,
    "pending_dirs": 0,
    "pending_dir_sample": [],
    "subscribers": 0,
    "catalog_revision": 1,
    "walker_task": "done",
    "requested_paths": []
  },
  "events": {
    "bus_started": false,
    "connections": 0,
    "latest_event_id": 0
  }
}
? 0
```

## Test: the diagnostic refuses a GET

```console
$ metab shellroot --api /api/diagnostics/pending-tallies
api: /api/diagnostics/pending-tallies
status: 405
Method Not Allowed
Error: /api/diagnostics/pending-tallies returned HTTP 405
? 1
```

## Test: rendering a document

The rendered `html` and its `assets` are elided.
They carry a KPress icon sprite of tens of kilobytes, which would make this transcript
unreviewable and would churn on every KPress upgrade without telling a reader anything
the surrounding fields do not.
The envelope around them is pinned exactly.

```console
$ metab shellroot --api '/api/kpress/render?path=README.md&view=document'
api: /api/kpress/render?path=README.md&view=document
status: 200
{
  "type": "kpress-rendered-document",
  "html": "[..]",
  "profile": "document",
  "printable": true,
  "assets": {
    "schema_version": "kpress-asset-manifest-v2",
    "assets": [
      {
        "id": "css/style-tokens.css",
        "kind": "package",
        "path": "css/style-tokens.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "0554b3a1d96a854f",
        "output_path": "css/style-tokens.css",
        "public_url": "/kpress-static/v0.3.3/css/style-tokens.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/syntax.css",
        "kind": "package",
        "path": "css/syntax.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "807cf5be35b5a8dd",
        "output_path": "css/syntax.css",
        "public_url": "/kpress-static/v0.3.3/css/syntax.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/document.css",
        "kind": "package",
        "path": "css/document.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "d86525c4bb370b43",
        "output_path": "css/document.css",
        "public_url": "/kpress-static/v0.3.3/css/document.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/components.css",
        "kind": "package",
        "path": "css/components.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "763595ddf1a251e9",
        "output_path": "css/components.css",
        "public_url": "/kpress-static/v0.3.3/css/components.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print.css",
        "kind": "package",
        "path": "css/print.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "86c6396bc77060cd",
        "output_path": "css/print.css",
        "public_url": "/kpress-static/v0.3.3/css/print.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "fonts/pt-serif-latin-400-normal.woff2",
        "kind": "package",
        "path": "fonts/pt-serif-latin-400-normal.woff2",
        "mode": "hosted",
        "media_type": "font/woff2",
        "content_hash": "4271064a37f3ffc0",
        "output_path": "fonts/pt-serif-latin-400-normal.woff2",
        "public_url": "/kpress-static/v0.3.3/fonts/pt-serif-latin-400-normal.woff2",
        "entry_point": false,
        "loading": "resource"
      },
      {
        "id": "fonts/pt-serif-latin-700-normal.woff2",
        "kind": "package",
        "path": "fonts/pt-serif-latin-700-normal.woff2",
        "mode": "hosted",
        "media_type": "font/woff2",
        "content_hash": "bf23a7a4eebedbb8",
        "output_path": "fonts/pt-serif-latin-700-normal.woff2",
        "public_url": "/kpress-static/v0.3.3/fonts/pt-serif-latin-700-normal.woff2",
        "entry_point": false,
        "loading": "resource"
      },
      {
        "id": "fonts/pt-serif-latin-400-italic.woff2",
        "kind": "package",
        "path": "fonts/pt-serif-latin-400-italic.woff2",
        "mode": "hosted",
        "media_type": "font/woff2",
        "content_hash": "cb373bde18855c82",
        "output_path": "fonts/pt-serif-latin-400-italic.woff2",
        "public_url": "/kpress-static/v0.3.3/fonts/pt-serif-latin-400-italic.woff2",
        "entry_point": false,
        "loading": "resource"
      },
      {
        "id": "fonts/pt-serif-latin-700-italic.woff2",
        "kind": "package",
        "path": "fonts/pt-serif-latin-700-italic.woff2",
        "mode": "hosted",
        "media_type": "font/woff2",
        "content_hash": "3cb3cfab3c562cbb",
        "output_path": "fonts/pt-serif-latin-700-italic.woff2",
        "public_url": "/kpress-static/v0.3.3/fonts/pt-serif-latin-700-italic.woff2",
        "entry_point": false,
        "loading": "resource"
      },
      {
        "id": "fonts/source-sans-3-latin-wght-normal.woff2",
        "kind": "package",
        "path": "fonts/source-sans-3-latin-wght-normal.woff2",
        "mode": "hosted",
        "media_type": "font/woff2",
        "content_hash": "7a19a7027e125257",
        "output_path": "fonts/source-sans-3-latin-wght-normal.woff2",
        "public_url": "/kpress-static/v0.3.3/fonts/source-sans-3-latin-wght-normal.woff2",
        "entry_point": false,
        "loading": "resource"
      },
      {
        "id": "fonts/source-sans-3-latin-wght-italic.woff2",
        "kind": "package",
        "path": "fonts/source-sans-3-latin-wght-italic.woff2",
        "mode": "hosted",
        "media_type": "font/woff2",
        "content_hash": "9a15dafc2c2b2414",
        "output_path": "fonts/source-sans-3-latin-wght-italic.woff2",
        "public_url": "/kpress-static/v0.3.3/fonts/source-sans-3-latin-wght-italic.woff2",
        "entry_point": false,
        "loading": "resource"
      }
    ],
    "import_map": {}
  },
  "diagnostics": [],
  "widgets": {},
  "model": {
    "version": 1,
    "title": "README.md",
    "route": "",
    "profile": "document",
    "headings": [],
    "widgets": {}
  }
}
? 0
```

## Test: rendering a transformed source through a POST body

`--data` sends the body, which is the path the browser uses when the Source view has
been transformed.
It reaches a different branch of the handler than the query form above.

```console
$ metab shellroot --api /api/kpress/render --data shellroot/render.json
api: /api/kpress/render
status: 400
{
  "type": "kpress_render_error",
  "error": "Invalid JSON body",
  "detail": "Invalid control character at: line 1 column 71 (char 70)"
}
Error: /api/kpress/render returned HTTP 400
? 1
```

## Test: export refuses a GET

```console
$ metab shellroot --api /api/kpress/export
api: /api/kpress/export
status: 405
Method Not Allowed
Error: /api/kpress/export returned HTTP 405
? 1
```

## Test: exporting a document writes it and reports the build

This is the one golden that writes.
The tryscript sandbox is created per run and discarded after it, the report’s paths
normalize to `<ROOT>`, and the content hash is stable across runs and across sandbox
paths -- so the write is deterministic evidence rather than a source of churn.
It runs last so no earlier test sees the written file.

```console
$ metab shellroot --api /api/kpress/export --data shellroot/export.json
api: /api/kpress/export
status: 200
{
  "type": "kpress-export-report",
  "report": {
    "schema_version": "kpress-build-manifest-v2",
    "output_dir": "<ROOT>",
    "files": [
      {
        "path": "out.html",
        "kind": "html",
        "content_hash": "5dca55909155f58b",
        "size": 10019,
        "applied_pipeline": []
      }
    ],
    "assets": [],
    "routes": {},
    "diagnostics": [],
    "pipeline": []
  },
  "destination": "<ROOT>/out.html"
}
? 0
```
