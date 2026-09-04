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
  mkdir -p hookroot &&
  cd hookroot &&
  printf '{"a": 1, "b": [2, 3]}\n' > data.json &&
  printf -- '--- a/x.txt\n+++ b/x.txt\n@@ -1 +1 @@\n-old\n+new\n' > change.patch &&
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
