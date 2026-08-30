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
  mkdir -p navroot/docs &&
  printf '# Sample\n' > navroot/README.md &&
  printf 'plain\n' > navroot/notes.txt &&
  printf 'nested\n' > navroot/docs/a.md &&
  touch -t 202311142213.20 navroot/README.md navroot/notes.txt navroot/docs/a.md
  navroot/docs navroot
---
# Golden tests: the navigation routes through `--api`

`/api/rollup` drives Folder Overview and the treemap, `/api/recent` the recency window,
and `/api/activity` the active-file badges.
None had a transcript.

Mtimes are pinned so the recency window and rollup tallies are deterministic.

`truncated` is reported here as `false`. The true case is not reachable from a golden
fixture: `max_files` is a hard-coded 500,000, with no request parameter to lower it, so
a truncated rollup needs a generated corpus rather than a sandbox.
`mb-crmq` carries that remainder.

## Test: a folder rollup

```console
$ metab navroot --api '/api/rollup?path=.&depth=1'
api: /api/rollup?path=.&depth=1
status: 200
{
  "root": "<ROOT>",
  "path": ".",
  "node": null,
  "ext_tallies": [],
  "file_type_breakdown": null,
  "index_status": "done",
  "indexed_files": 3,
  "max_files": 500000,
  "truncated": false
}
? 0
```

## Test: a rollup with no children

```console
$ metab navroot --api '/api/rollup?path=docs&depth=0'
api: /api/rollup?path=docs&depth=0
status: 200
{
  "root": "<ROOT>",
  "path": "docs",
  "node": {
    "name": "docs",
    "path": "docs",
    "type": "dir",
    "state": "complete",
    "total_files": 1,
    "total_size": 7,
    "unignored_files": 1,
    "unignored_size": 7,
    "mtime": 1700000000.0,
    "gitignored": false,
    "dominant_ext": ".md",
    "children": null
  },
  "ext_tallies": [
    [
      ".md",
      1,
      7,
      1,
      7
    ]
  ],
  "file_type_breakdown": {
    "schema": "file-type-breakdown-v1",
    "registry": {
      "schema_version": 3,
      "revision": 3,
      "fingerprint": "89cd0f4edf740666cb23ba43cc4a305f035f92b78f540673e76cc09445932c8c"
    },
    "metrics": {
      "all": {
        "files": 1,
        "bytes": 7
      },
      "unignored": {
        "files": 1,
        "bytes": 7
      }
    },
    "groups": [
      {
        "id": "docs",
        "families": [
          {
            "id": "markdown",
            "metrics": {
              "all": {
                "files": 1,
                "bytes": 7
              },
              "unignored": {
                "files": 1,
                "bytes": 7
              }
            },
            "extensions": [
              {
                "extension": ".md",
                "metrics": {
                  "all": {
                    "files": 1,
                    "bytes": 7
                  },
                  "unignored": {
                    "files": 1,
                    "bytes": 7
                  }
                }
              }
            ]
          }
        ]
      }
    ],
    "no_extension": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "filenames": [],
      "others": null
    },
    "remaining_types": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "extensions": [],
      "others": null
    }
  },
  "index_status": "done",
  "indexed_files": 3,
  "max_files": 500000,
  "truncated": false
}
? 0
```

## Test: the recency window

```console
$ metab navroot --api '/api/recent?window=24h'
api: /api/recent?window=24h
status: 200
{
  "root": "<ROOT>",
  "entries_flat": [],
  "gitignored_dirs": [],
  "window": "24h",
  "limit": 5000,
  "total_matching": 0,
  "truncated": false,
  "tally_cache_status": "done"
}
? 0
```

## Test: a recency window that excludes the fixture’s pinned mtimes

```console
$ metab navroot --api '/api/recent?window=live'
api: /api/recent?window=live
status: 200
{
  "root": "<ROOT>",
  "entries_flat": [],
  "gitignored_dirs": [],
  "window": "live",
  "limit": 5000,
  "total_matching": 0,
  "truncated": false,
  "tally_cache_status": "done"
}
? 0
```

## Test: active files

```console
$ metab navroot --api /api/activity
api: /api/activity
status: 200
{
  "active_files": [],
  "poll_interval_ms": 5000
}
? 0
```
