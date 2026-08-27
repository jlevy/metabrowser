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
  mkdir -p walkroot/logs &&
  printf '# Sample\n\nHello.\n' > walkroot/README.md &&
  printf '{"event": "start"}\n{"event": "stop"}\n' > walkroot/data.jsonl &&
  printf 'line one\nline two\n' > walkroot/logs/run.log &&
  touch -t 202311142213.20 walkroot/README.md walkroot/data.jsonl
  walkroot/logs/run.log walkroot/logs walkroot
---
# Golden tests: walk mode

Walk mode in every output format, including streaming and subtree walks.
The `before` command builds a small fixture tree in the sandbox with pinned mtimes
(`touch -t` under `TZ=UTC`, epoch 1700000000) so sizes and timestamps in walker output
are deterministic.

## Test: walk text output

```console
$ metab walkroot --walk
walk: walkroot
status: done
counts: files=3 dirs=2 symlinks=0
totals: total_files=3 total_size=72

entries:
  . [dir] files=3 size=72
  README.md [file] size=17
  data.jsonl [file] size=37
  logs [dir] files=1 size=18
  logs/run.log [file] size=18
? 0
```

## Test: walk text summary detail

```console
$ metab walkroot --walk --detail summary
walk: walkroot
status: done
counts: files=3 dirs=2 symlinks=0
totals: total_files=3 total_size=72
? 0
```

## Test: walk JSON envelope

```console
$ metab walkroot --walk --format json
{
  "root": "[CWD]/walkroot",
  "tree": [
    {
      "name": "logs",
      "path": "logs",
      "type": "dir",
      "total_files": 1,
      "total_size": 18,
      "mtime": 1700000000.0,
      "has_children": true,
      "children": [
        {
          "name": "run.log",
          "path": "logs/run.log",
          "type": "file",
          "size": 18,
          "mtime": 1700000000.0,
          "ext": ".log"
        }
      ]
    },
    {
      "name": "README.md",
      "path": "README.md",
      "type": "file",
      "size": 17,
      "mtime": 1700000000.0,
      "ext": ".md"
    },
    {
      "name": "data.jsonl",
      "path": "data.jsonl",
      "type": "file",
      "size": 37,
      "mtime": 1700000000.0,
      "ext": ".jsonl"
    }
  ],
  "filtered": null,
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000
}
? 0
```

## Test: walk YAML envelope

```console
$ metab walkroot --walk --format yaml
root: [CWD]/walkroot
tree:
- name: logs
  path: logs
  type: dir
  total_files: 1
  total_size: 18
  mtime: 1700000000.0
  has_children: true
  children:
  - name: run.log
    path: logs/run.log
    type: file
    size: 18
    mtime: 1700000000.0
    ext: .log
- name: README.md
  path: README.md
  type: file
  size: 17
  mtime: 1700000000.0
  ext: .md
- name: data.jsonl
  path: data.jsonl
  type: file
  size: 37
  mtime: 1700000000.0
  ext: .jsonl
filtered: null
tally_cache_status: done
tally_cache_max_files: 500000
? 0
```

## Test: walk JSON streaming (one record per line)

```console
$ metab walkroot --walk --format json --stream
{"path":"","parent":"","name":"walkroot","type":"dir","ext":"","kind":"dir","size":0,"mtime_ns":0,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":null,"total_size":null,"unignored_files":null,"unignored_size":null,"newest_mtime_ns":null,"gitignored":false,"write_token":null}
{"path":"logs","parent":"","name":"logs","type":"dir","ext":"","kind":"dir","size":0,"mtime_ns":0,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":null,"total_size":null,"unignored_files":null,"unignored_size":null,"newest_mtime_ns":null,"gitignored":false,"write_token":null}
{"path":"README.md","parent":"","name":"README.md","type":"file","ext":".md","kind":"file","size":17,"mtime_ns":1700000000000000000,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":null,"total_size":null,"unignored_files":null,"unignored_size":null,"newest_mtime_ns":null,"gitignored":false,"write_token":null}
{"path":"data.jsonl","parent":"","name":"data.jsonl","type":"file","ext":".jsonl","kind":"file","size":37,"mtime_ns":1700000000000000000,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":null,"total_size":null,"unignored_files":null,"unignored_size":null,"newest_mtime_ns":null,"gitignored":false,"write_token":null}
{"path":"logs/run.log","parent":"logs","name":"run.log","type":"file","ext":".log","kind":"file","size":18,"mtime_ns":1700000000000000000,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":null,"total_size":null,"unignored_files":null,"unignored_size":null,"newest_mtime_ns":null,"gitignored":false,"write_token":null}
{"path":"logs","parent":"","name":"logs","type":"dir","ext":"","kind":"dir","size":0,"mtime_ns":1700000000000000000,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":1,"total_size":18,"unignored_files":1,"unignored_size":18,"newest_mtime_ns":1700000000000000000,"gitignored":false,"write_token":null}
{"path":"","parent":"","name":"walkroot","type":"dir","ext":"","kind":"dir","size":0,"mtime_ns":1700000000000000000,"mtime_hash":"","active":false,"views":[],"labels":[],"total_files":3,"total_size":72,"unignored_files":3,"unignored_size":72,"newest_mtime_ns":1700000000000000000,"gitignored":false,"write_token":null}
? 0
```

## Test: walk JSON subtree via --path

```console
$ metab walkroot --walk --format json --path logs
{
  "root": "[CWD]/walkroot",
  "tree": [
    {
      "name": "run.log",
      "path": "logs/run.log",
      "type": "file",
      "size": 18,
      "mtime": 1700000000.0,
      "ext": ".log"
    }
  ],
  "filtered": null,
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000
}
? 0
```
