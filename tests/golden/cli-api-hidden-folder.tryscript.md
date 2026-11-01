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
  mkdir -p hiddenroot/.hidden/sub hiddenroot/.logs hiddenroot/shown/nested &&
  printf '# Hidden\n' > hiddenroot/.hidden/README.md &&
  printf 'plain\n' > hiddenroot/.hidden/notes.txt &&
  printf 'plain\n' > hiddenroot/.logs/run.txt &&
  printf 'plain\n' > hiddenroot/shown/notes.txt &&
  ln -s shown hiddenroot/link &&
  touch -t 202311142213.20 hiddenroot/.hidden/README.md hiddenroot/.hidden/notes.txt
  hiddenroot/.logs/run.txt hiddenroot/shown/notes.txt hiddenroot/shown/nested
  hiddenroot/.hidden/sub hiddenroot/.hidden hiddenroot/.logs hiddenroot/shown hiddenroot &&
  touch -h -t 202311142213.20 hiddenroot/link
---
# Golden tests: a folder the inventory leaves out says so

The inventory’s scope leaves out hidden path components and does not follow symbolic
links, so a folder reached either way has no tree and no rollup, and its aggregates stay
null.
`/api/file` still answers it with the folder envelope, so its page and README show.
`dir.not_indexed` names which it is, and the page says why it has no totals instead of
waiting for them.
A file inside the folder opens at its own address, and a dot-folder the
inventory does list is an ordinary folder with no such key.

## Test: a hidden folder keeps its envelope and its README

```console
$ metab hiddenroot --api '/api/file?path=.hidden/'
api: /api/file?path=.hidden/
status: 200
{
  "type": "folder",
  "kind": "folder",
  "path": ".hidden",
  "name": ".hidden",
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
    "total_files": null,
    "total_size": null,
    "unignored_files": null,
    "unignored_size": null,
    "mtime": null,
    "gitignored": false,
    "state": "pending",
    "not_indexed": "hidden"
  },
  "readme_path": ".hidden/README.md",
  "readme_search_truncated": false
}
? 0
```

## Test: so does a folder under a hidden one

```console
$ metab hiddenroot --api '/api/file?path=.hidden/sub'
api: /api/file?path=.hidden/sub
status: 200
{
  "type": "folder",
  "kind": "folder",
  "path": ".hidden/sub",
  "name": "sub",
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
    "total_files": null,
    "total_size": null,
    "unignored_files": null,
    "unignored_size": null,
    "mtime": null,
    "gitignored": false,
    "state": "pending",
    "not_indexed": "hidden"
  },
  "readme_path": "",
  "readme_search_truncated": false
}
? 0
```

## Test: the tree and the rollup have nothing to say about it

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

## Test: a symbolic link to a folder, and a folder through one

```console
$ metab hiddenroot --api '/api/file?path=link/'
api: /api/file?path=link/
status: 200
{
  "type": "folder",
  "kind": "folder",
  "path": "link",
  "name": "shown",
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
    "total_files": null,
    "total_size": null,
    "unignored_files": null,
    "unignored_size": null,
    "mtime": null,
    "gitignored": false,
    "state": "pending",
    "not_indexed": "symlink"
  },
  "readme_path": "",
  "readme_search_truncated": false
}
? 0
```

```console
$ metab hiddenroot --api '/api/file?path=link/nested'
api: /api/file?path=link/nested
status: 200
{
  "type": "folder",
  "kind": "folder",
  "path": "link/nested",
  "name": "nested",
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
    "total_files": null,
    "total_size": null,
    "unignored_files": null,
    "unignored_size": null,
    "mtime": null,
    "gitignored": false,
    "state": "pending",
    "not_indexed": "symlink"
  },
  "readme_path": "",
  "readme_search_truncated": false
}
? 0
```

```console
$ metab hiddenroot --api '/api/rollup?path=link' 2>&1
api: /api/rollup?path=link
status: 404
{
  "error": "Not found"
}
Error: /api/rollup?path=link returned HTTP 404
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
