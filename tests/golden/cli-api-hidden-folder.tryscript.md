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
  mkdir -p hiddenroot/.hidden/sub hiddenroot/.logs hiddenroot/shown &&
  printf 'plain\n' > hiddenroot/.hidden/notes.txt &&
  printf 'plain\n' > hiddenroot/.logs/run.txt &&
  printf 'plain\n' > hiddenroot/shown/notes.txt &&
  touch -t 202311142213.20 hiddenroot/.hidden/notes.txt hiddenroot/.logs/run.txt
  hiddenroot/shown/notes.txt hiddenroot/.hidden/sub hiddenroot/.hidden hiddenroot/.logs
  hiddenroot/shown hiddenroot
---
# Golden tests: a hidden folder has no view, and says why

The inventory’s scope leaves hidden path components out, so a hidden folder has no tree
and no rollup. `/api/file` used to answer one with a folder envelope whose aggregates
stayed pending forever, and the page showed “Could not load file types.”
beside a skeleton that never finished.
It now answers with the reason, which the page shows in place of a folder view.
A file inside the folder still opens at its own address, and a dot-folder the inventory
does list is an ordinary folder.

## Test: the three routes agree on a hidden folder, and the file route says why

```console
$ metab hiddenroot --api '/api/file?path=.hidden/' 2>&1
api: /api/file?path=.hidden/
status: 404
{
  "summary": "Could not open this folder.",
  "error": "Metabrowser does not index hidden folders, so this one has no view. A file inside it still opens at its own address."
}
Error: /api/file?path=.hidden/ returned HTTP 404
? 1
```

```console
$ metab hiddenroot --api '/api/tree?path=.hidden' 2>&1
api: /api/tree?path=.hidden
status: 404
{
  "error": "Not found"
}
Error: /api/tree?path=.hidden returned HTTP 404
? 1
```

```console
$ metab hiddenroot --api '/api/rollup?path=.hidden' 2>&1
api: /api/rollup?path=.hidden
status: 404
{
  "error": "Not found"
}
Error: /api/rollup?path=.hidden returned HTTP 404
? 1
```

## Test: so does a folder under a hidden one

```console
$ metab hiddenroot --api '/api/file?path=.hidden/sub' 2>&1
api: /api/file?path=.hidden/sub
status: 404
{
  "summary": "Could not open this folder.",
  "error": "Metabrowser does not index hidden folders, so this one has no view. A file inside it still opens at its own address."
}
Error: /api/file?path=.hidden/sub returned HTTP 404
? 1
```

## Test: a file inside a hidden folder still opens

```console
$ metab hiddenroot --api '/api/file?path=.hidden/notes.txt'
api: /api/file?path=.hidden/notes.txt
status: 200
{
  "type": "text",
  "kind": "text",
  "views": [
    {
      "id": "source",
      "label": "Source",
      "default": true,
      "container_class": "content-body metabrowser-source-host",
      "printable": true,
      "print_profile": "source",
      "render_runtime": "client"
    }
  ],
  "path": ".hidden/notes.txt",
  "ext": ".txt",
  "size": 6,
  "mtime_hash": "notes_txt_6_1700000000000000000_8ahuh1mrwyb73n3ig7yp3gxtec9j4ck",
  "content": "plain\n",
  "content_offset": 0,
  "content_bytes": 6,
  "bytes_read": 6,
  "content_truncated": false,
  "content_preview_limit": 2097152,
  "content_max_preview_limit": 16777216,
  "highlight_disabled": false
}
? 0
```

## Test: a dot-folder on the inventory’s allowlist is an ordinary folder

```console
$ metab hiddenroot --api '/api/file?path=.logs/'
api: /api/file?path=.logs/
status: 200
{
  "type": "folder",
  "kind": "folder",
  "path": ".logs",
  "name": ".logs",
  "views": [
    {
      "id": "overview",
      "label": "Overview",
      "default": true,
      "container_class": "content-body folder-overview-host",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    },
    {
      "id": "treemap",
      "label": "Treemap",
      "default": false,
      "container_class": "content-body folder-treemap-host",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    }
  ],
  "dir": {
    "total_files": 1,
    "total_size": 6,
    "unignored_files": 1,
    "unignored_size": 6,
    "mtime": 1700000000.0,
    "gitignored": false,
    "state": "complete"
  },
  "readme_path": "",
  "readme_search_truncated": false
}
? 0
```
