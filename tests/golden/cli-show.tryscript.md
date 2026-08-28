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
  mkdir -p showroot/docs &&
  printf '# Sample\n\nHello.\n' > showroot/README.md &&
  printf 'plain text\n' > showroot/notes.txt &&
  printf '{"name": "sample", "version": 1}\n' > showroot/data.json &&
  printf -- '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n' > showroot/change.patch &&
  printf '{"type":"system","subtype":"init","session_id":"s1","model":"m1"}\n' > showroot/session.jsonl &&
  printf '{"event":"start"}\n{"event":"stop"}\n' > showroot/events.jsonl &&
  printf '\x00\x01\x02binary\n' > showroot/blob.bin &&
  printf 'nested\n' > showroot/docs/a.md &&
  touch -t 202311142213.20 showroot/README.md showroot/notes.txt showroot/data.json
  showroot/change.patch showroot/session.jsonl showroot/events.jsonl showroot/blob.bin
  showroot/docs/a.md showroot/docs showroot
---
# Golden tests: `--show`, the four layers for one selection

`--show` answers “what would the browser do with this path”: the route it resolves to,
the kind it classifies as, the views it offers, and a summary of the model behind them.

This is the transcript for `/api/file`, which decides the tabs a reader sees for every
selection. One file of each built-in kind appears below, so a kind losing a view, or a
view losing its default, changes this file.

## Test: markdown

```console
$ metab showroot --show README.md
show: README.md
route: /view/README.md
kind: markdown
views: rendered (default), source
model: text envelope; size=17 content_bytes=17 content_truncated=False
? 0
```

## Test: plain text

```console
$ metab showroot --show notes.txt
show: notes.txt
route: /view/notes.txt
kind: text
views: source (default)
model: text envelope; size=11 content_bytes=11 content_truncated=False
? 0
```

## Test: structured data

```console
$ metab showroot --show data.json
show: data.json
route: /view/data.json
kind: structured
views: tree (default), source
model: text envelope; size=33 content_bytes=33 content_truncated=False
? 0
```

## Test: a patch file

```console
$ metab showroot --show change.patch
show: change.patch
route: /view/change.patch
kind: diff
views: diff (default)
model: text envelope; size=38 content_bytes=38 content_truncated=False
? 0
```

## Test: an agent session log

```console
$ metab showroot --show session.jsonl
show: session.jsonl
route: /view/session.jsonl
kind: agent-log
views: log (default), charts, raw
model: jsonl envelope; size=66
? 0
```

## Test: JSONL with no recognized adapter

```console
$ metab showroot --show events.jsonl
show: events.jsonl
route: /view/events.jsonl
kind: unknown-jsonl
views: log (default), raw
model: jsonl envelope; size=35
? 0
```

## Test: binary

```console
$ metab showroot --show blob.bin
show: blob.bin
route: /view/blob.bin
kind: binary
views: bytes (default)
model: binary envelope; size=10
? 0
```

## Test: a folder

```console
$ metab showroot --show docs
show: docs
route: /view/docs
kind: folder
views: overview (default), treemap
model: folder envelope; readme_path=
? 0
```

## Test: JSON output carries the same four layers

```console
$ metab showroot --show README.md --format json
{
  "show": "README.md",
  "route": "/view/README.md",
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
  "model": "text envelope; size=17 content_bytes=17 content_truncated=False"
}
? 0
```
