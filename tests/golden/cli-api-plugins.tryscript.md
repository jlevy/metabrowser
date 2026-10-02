---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
  GIT_AUTHOR_NAME: "Test"
  GIT_AUTHOR_EMAIL: "test@example.com"
  GIT_COMMITTER_NAME: "Test"
  GIT_COMMITTER_EMAIL: "test@example.com"
  GIT_AUTHOR_DATE: "2020-01-01T00:00:00Z"
  GIT_COMMITTER_DATE: "2020-01-01T00:00:00Z"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  mkdir -p hookroot rejplugin/rejdiff &&
  printf '[plugin]\nname = "rejdiff"\nsdk_version = "0.7"\n[[kind]]\nid = "diff"\nmatch = { exts = [".rej"] }\npriority = 10\n' > rejplugin/rejdiff/manifest.toml &&
  printf '// The built-in diff plugin draws the view.\n' > rejplugin/rejdiff/index.js &&
  cd hookroot &&
  printf '{"a": 1, "b": [2, 3]}\n' > data.json &&
  printf -- '--- a/x.txt\n+++ b/x.txt\n@@ -1 +1 @@\n-old\n+new\n' > change.patch &&
  printf -- '--- a/y.txt\n+++ b/y.txt\n@@ -1 +1 @@\n-was\n+is\n' > change.rej &&
  printf '{"type":"system","subtype":"init","session_id":"s1","model":"m1"}\n' > session.jsonl &&
  printf '\000\001\002bin' > blob.bin &&
  git init -q --initial-branch=main . &&
  printf 'first\n' > tracked.txt &&
  git add tracked.txt &&
  git commit -q -m 'first commit' &&
  touch -t 202311142213.20 data.json change.patch session.jsonl blob.bin
---
# Golden tests: the built-in plugin data hooks

Six `[[data_hook]]` routes back four kinds’ models.
Each is reachable at `/api/plugin/<plugin>/<route>`, and none had a transcript.

## Test: structured data parsed into a tree

```console
$ metab hookroot --api '/api/plugin/structured/parsed?path=data.json'
api: /api/plugin/structured/parsed?path=data.json
status: 200
{
  "type": "structured",
  "path": "data.json",
  "ext": ".json",
  "mtime_hash": "data_json_22_1700000000000000000_oxzwjuzo4dpggg9x1isunq5frrzx07a",
  "size": 22,
  "parsed": {
    "a": 1,
    "b": [
      2,
      3
    ]
  },
  "pretty_yaml": "a: 1\nb:\n  - 2\n  - 3\n",
  "node_count": 5,
  "max_depth": 2,
  "comments_supported": false,
  "parse_error": null,
  "truncated": false
}
? 0
```

## Test: a structured cache of size zero still answers

`STRUCTURED_CACHE_SIZE` is an operator setting.
Zero, or less, caches nothing and every request parses; it is not an error.

```console
$ STRUCTURED_CACHE_SIZE=0 metab hookroot --api '/api/plugin/structured/parsed?path=data.json'
api: /api/plugin/structured/parsed?path=data.json
status: 200
{
  "type": "structured",
  "path": "data.json",
  "ext": ".json",
  "mtime_hash": "data_json_22_1700000000000000000_oxzwjuzo4dpggg9x1isunq5frrzx07a",
  "size": 22,
  "parsed": {
    "a": 1,
    "b": [
      2,
      3
    ]
  },
  "pretty_yaml": "a: 1\nb:\n  - 2\n  - 3\n",
  "node_count": 5,
  "max_depth": 2,
  "comments_supported": false,
  "parse_error": null,
  "truncated": false
}
? 0
```

## Test: a negative parse cap answers truncated

`STRUCTURED_PARSE_MAX_BYTES` is an operator setting too.
Nothing fits under a cap below zero, so the file is not read and the Tree view falls
back to Source.

```console
$ STRUCTURED_PARSE_MAX_BYTES=-1 metab hookroot --api '/api/plugin/structured/parsed?path=data.json'
api: /api/plugin/structured/parsed?path=data.json
status: 200
{
  "type": "structured",
  "path": "data.json",
  "ext": ".json",
  "mtime_hash": "data_json_22_1700000000000000000_oxzwjuzo4dpggg9x1isunq5frrzx07a",
  "size": 22,
  "parsed": null,
  "pretty_yaml": "",
  "node_count": 0,
  "max_depth": 0,
  "comments_supported": false,
  "parse_error": null,
  "truncated": true
}
? 0
```

## Test: a bounded byte chunk

```console
$ metab hookroot --api '/api/plugin/binary/chunk?path=blob.bin&offset=0&limit=4'
api: /api/plugin/binary/chunk?path=blob.bin&offset=0&limit=4
status: 200
{
  "type": "binary_chunk",
  "path": "blob.bin",
  "offset": 0,
  "bytes_read": 4,
  "next_offset": 4,
  "logical_size": 6,
  "max_preview_bytes": 33554432,
  "has_more": true,
  "preview_limited": false,
  "mtime_hash": "blob_bin_6_1700000000000000000_ek42qv3e8bektxrxugw0221o2uupcq0",
  "content_base64": "AAECYg=="
}
? 0
```

## Test: a byte bound below zero reads nothing

The bytes view has three settings, and each is taken below zero.
A default chunk size below zero, and a requested limit clamped to a maximum below zero,
read nothing and say whether bytes remain.

```console
$ METABROWSER_BINARY_PREVIEW_BYTES=-1 metab hookroot --api '/api/plugin/binary/chunk?path=blob.bin'
api: /api/plugin/binary/chunk?path=blob.bin
status: 200
{
  "type": "binary_chunk",
  "path": "blob.bin",
  "offset": 0,
  "bytes_read": 0,
  "next_offset": 0,
  "logical_size": 6,
  "max_preview_bytes": 33554432,
  "has_more": true,
  "preview_limited": false,
  "mtime_hash": "blob_bin_6_1700000000000000000_ek42qv3e8bektxrxugw0221o2uupcq0",
  "content_base64": ""
}
? 0
```

```console
$ METABROWSER_BINARY_PREVIEW_MAX_CHUNK_BYTES=-1 metab hookroot --api '/api/plugin/binary/chunk?path=blob.bin&offset=2&limit=4'
api: /api/plugin/binary/chunk?path=blob.bin&offset=2&limit=4
status: 200
{
  "type": "binary_chunk",
  "path": "blob.bin",
  "offset": 2,
  "bytes_read": 0,
  "next_offset": 2,
  "logical_size": 6,
  "max_preview_bytes": 33554432,
  "has_more": true,
  "preview_limited": false,
  "mtime_hash": "blob_bin_6_1700000000000000000_ek42qv3e8bektxrxugw0221o2uupcq0",
  "content_base64": ""
}
? 0
```

Nothing is inside a ceiling below zero.
The first window is empty and says the preview is limited, and there is no later window:
an offset is clamped to the ceiling, which is no place in the file.

```console
$ METABROWSER_BINARY_PREVIEW_MAX_BYTES=-1 metab hookroot --api '/api/plugin/binary/chunk?path=blob.bin'
api: /api/plugin/binary/chunk?path=blob.bin
status: 200
{
  "type": "binary_chunk",
  "path": "blob.bin",
  "offset": 0,
  "bytes_read": 0,
  "next_offset": 0,
  "logical_size": 6,
  "max_preview_bytes": -1,
  "has_more": false,
  "preview_limited": true,
  "mtime_hash": "blob_bin_6_1700000000000000000_ek42qv3e8bektxrxugw0221o2uupcq0",
  "content_base64": ""
}
? 0
```

```console
$ METABROWSER_BINARY_PREVIEW_MAX_BYTES=-1 metab hookroot --api '/api/plugin/binary/chunk?path=blob.bin&offset=2'
api: /api/plugin/binary/chunk?path=blob.bin&offset=2
status: 404
{
  "type": "binary_chunk_error",
  "error": "This file is no longer available.",
  "path": "blob.bin"
}
Error: /api/plugin/binary/chunk?path=blob.bin&offset=2 returned HTTP 404
? 1
```

## Test: agent-log charts

```console
$ metab hookroot --api '/api/plugin/agent-log/charts?path=session.jsonl'
api: /api/plugin/agent-log/charts?path=session.jsonl
status: 200
{
  "summary": {
    "counts": {
      "init": 1
    },
    "metadata": {
      "adapter": "claude",
      "model": "m1"
    }
  },
  "charts": []
}
? 0
```

## Test: a patch file as a File Diff Format document

```console
$ metab hookroot --api '/api/plugin/diff/document?path=change.patch'
api: /api/plugin/diff/document?path=change.patch
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "patch:7058786980005761",
    "source": {
      "name": "patch"
    },
    "kind": "content",
    "base_policy": "direct",
    "left": {
      "kind": "patch"
    },
    "right": {
      "kind": "patch"
    },
    "options": {
      "context": 3,
      "rename_detection": true
    },
    "warnings": []
  },
  "manifest": {
    "files": [
      {
        "id": "f1",
        "kind": "modified",
        "old": {
          "path": "x.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "empty"
          }
        },
        "new": {
          "path": "x.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "empty"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 1
      }
    ],
    "totals": {
      "files": 1,
      "additions": 1,
      "deletions": 1,
      "exact": true
    },
    "truncated": false
  },
  "patches": {
    "f1": {
      "file_id": "f1",
      "hunks": [
        {
          "old_start": 1,
          "old_count": 1,
          "new_start": 1,
          "new_count": 1,
          "lines": [
            {
              "op": "del",
              "text": "old",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "new",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    }
  }
}
? 0
```

## Test: a file a plugin made the diff kind, under another name

A plugin may add match rules to a built-in kind.
This one makes `.rej` files the `diff` kind, so `/api/file` sends the Diff view to
`change.rej`.

```console
$ metab hookroot --plugins-dir rejplugin --api '/api/file?path=change.rej' > file.txt
? 0
```

```console
$ grep -E '^  "(kind|path)":|^      "(id|label)":' file.txt
  "kind": "diff",
      "id": "diff",
      "label": "Diff",
  "path": "change.rej",
? 0
```

The view’s data request is then answered whatever the file is called, with the changes
the file holds.

```console
$ metab hookroot --plugins-dir rejplugin --api '/api/plugin/diff/document?path=change.rej' > document.txt
? 0
```

```console
$ grep -E '^status|"(op|text|path|warnings)":' document.txt
status: 200
    "warnings": []
          "path": "y.txt",
          "path": "y.txt",
              "op": "del",
              "text": "was",
              "op": "add",
              "text": "is",
? 0
```

## Test: a file that holds no diff is an empty change set, not a missing file

```console
$ metab hookroot --api '/api/plugin/diff/document?path=tracked.txt'
api: /api/plugin/diff/document?path=tracked.txt
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "patch:b640e840b19d3786",
    "source": {
      "name": "patch"
    },
    "kind": "content",
    "base_policy": "direct",
    "left": {
      "kind": "patch"
    },
    "right": {
      "kind": "patch"
    },
    "options": {
      "context": 3,
      "rename_detection": true
    },
    "warnings": [
      "no diff sections recognized in this input"
    ]
  },
  "manifest": {
    "files": [],
    "totals": {
      "files": 0,
      "additions": 0,
      "deletions": 0,
      "exact": true
    },
    "truncated": false
  },
  "patches": {}
}
? 0
```

## Test: the entries inside a patch container

```console
$ metab hookroot --api '/api/plugin/diff/children?path=change.patch'
api: /api/plugin/diff/children?path=change.patch
status: 200
{
  "children": [
    {
      "name": "x.txt",
      "path": "change.patch/x.txt",
      "badge": "M"
    }
  ],
  "truncated": false
}
? 0
```

## Test: a comparison naming neither endpoint is refused

```console
$ metab hookroot --api '/api/plugin/diff/comparison'
api: /api/plugin/diff/comparison
status: 400
{
  "error": "diff_comparison",
  "message": "Name a revision, or both endpoints of a comparison.",
  "path": ".."
}
Error: /api/plugin/diff/comparison returned HTTP 400
? 1
```
