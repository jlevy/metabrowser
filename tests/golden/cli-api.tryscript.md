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
  mkdir -p apiroot &&
  printf '# Sample\n\nHello.\n' > apiroot/README.md &&
  printf 'plain\n' > apiroot/notes.txt &&
  touch -t 202311142213.20 apiroot/README.md apiroot/notes.txt apiroot
---
# Golden tests: `--api` wire parity

`--api` issues one route through the real ASGI stack — the same middleware, routing, and
serialization the browser reaches — and prints the normalized envelope.
`--walk` and `--diff` reach their models through the library instead, so they prove the
model and not the wire.

The fixture pins mtimes (`touch -t` under `TZ=UTC`, epoch 1700000000) so timestamps are
deterministic, and the served root normalizes to `[ROOT]` so the sandbox path never
reaches the transcript.

## Test: a tree envelope through the route

```console
$ metab apiroot --api '/api/tree?depth=1'
api: /api/tree?depth=1
status: 200
{
  "root": "<ROOT>",
  "tree": [
    {
      "name": "README.md",
      "path": "README.md",
      "type": "file",
      "size": 17,
      "mtime": 1700000000.0,
      "ext": ".md"
    },
    {
      "name": "notes.txt",
      "path": "notes.txt",
      "type": "file",
      "size": 6,
      "mtime": 1700000000.0,
      "ext": ".txt"
    }
  ],
  "filtered": null,
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000,
  "summary": null,
  "file_type_registry": null,
  "extensions": null,
  "canonical_extensions": null,
  "type_families": null,
  "type_presets": null,
  "recency_tallies": null
}
? 0
```

## Test: a file selection carries its kind and view list

This is the surface the parity plan called the biggest gap: `/api/file` decides the tabs
a reader sees, and nothing outside a browser proved it.

```console
$ metab apiroot --api '/api/file?path=README.md'
api: /api/file?path=README.md
status: 200
{
  "type": "text",
  "kind": "markdown",
  "views": [
    {
      "id": "rendered",
      "label": "Document",
      "default": true,
      "container_class": "content-body metabrowser-kpress-host md-body",
      "printable": true,
      "print_profile": "document",
      "render_runtime": "kpress"
    },
    {
      "id": "source",
      "label": "Source",
      "default": false,
      "container_class": "content-body metabrowser-source-host",
      "printable": true,
      "print_profile": "source",
      "render_runtime": "client"
    }
  ],
  "path": "README.md",
  "ext": ".md",
  "size": 17,
  "mtime_hash": "README_md_17_1700000000000000000_g2zgranz5n3p809yrp44i27596jw754",
  "content": "# Sample\n\nHello.\n",
  "content_offset": 0,
  "content_bytes": 17,
  "bytes_read": 17,
  "content_truncated": false,
  "content_preview_limit": 524288,
  "content_max_preview_limit": 16777216,
  "highlight_disabled": false
}
? 0
```

## Test: query parameters are parsed by the route, not the library

A type filter reaches the route and changes the envelope: `notes.txt` drops out and a
`filtered` summary appears.
A library-level transcript cannot show this.

```console
$ metab apiroot --api '/api/tree?depth=1&types=.md'
api: /api/tree?depth=1&types=.md
status: 200
{
  "root": "<ROOT>",
  "tree": [
    {
      "name": "README.md",
      "path": "README.md",
      "type": "file",
      "size": 17,
      "mtime": 1700000000.0,
      "ext": ".md"
    }
  ],
  "filtered": {
    "files": 1,
    "size": 17,
    "entries": 1
  },
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000,
  "summary": null,
  "file_type_registry": null,
  "extensions": null,
  "canonical_extensions": null,
  "type_families": null,
  "type_presets": null,
  "recency_tallies": null
}
? 0
```

## Test: YAML rendering of the same envelope

```console
$ metab apiroot --api '/api/tree?depth=1' --format yaml
api: /api/tree?depth=1
status: 200
root: <ROOT>
tree:
- name: README.md
  path: README.md
  type: file
  size: 17
  mtime: 1700000000.0
  ext: .md
- name: notes.txt
  path: notes.txt
  type: file
  size: 6
  mtime: 1700000000.0
  ext: .txt
filtered: null
tally_cache_status: done
tally_cache_max_files: 500000
summary: null
file_type_registry: null
extensions: null
canonical_extensions: null
type_families: null
type_presets: null
recency_tallies: null
? 0
```

## Test: a missing path reports its status and exits non-zero

```console
$ metab apiroot --api '/api/file?path=missing.md'
api: /api/file?path=missing.md
status: 404
{
  "summary": "Could not open this file.",
  "error": "This file is no longer available."
}
Error: /api/file?path=missing.md returned HTTP 404
? 1
```

## Test: a route outside the API surface is rejected

```console
$ metab apiroot --api /etc/passwd
Error: route must begin with /api/; got /etc/passwd
? 1
```
