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
  mkdir -p groupsroot/docs groupsroot/src groupsroot/data groupsroot/logs groupsroot/misc &&
  printf '# Sample\n' > groupsroot/README.md &&
  printf 'plain\n' > groupsroot/notes.txt &&
  printf '# Guide\n' > groupsroot/docs/guide.md &&
  printf 'print(1)\n' > groupsroot/src/app.py &&
  printf 'export {};\n' > groupsroot/src/util.js &&
  printf 'all:\n' > groupsroot/Makefile &&
  printf '{}\n' > groupsroot/data/config.json &&
  printf 'started\n' > groupsroot/logs/run.log &&
  printf 'opaque\n' > groupsroot/misc/blob.xyz &&
  touch -t 202311142213.20 groupsroot/README.md groupsroot/notes.txt groupsroot/docs/guide.md
  groupsroot/src/app.py groupsroot/src/util.js groupsroot/Makefile groupsroot/data/config.json
  groupsroot/logs/run.log groupsroot/misc/blob.xyz groupsroot/docs groupsroot/src
  groupsroot/data groupsroot/logs groupsroot/misc groupsroot &&
  mkdir -p agesroot &&
  printf 'old\n' > agesroot/old.md &&
  touch -t 202311142213.20 agesroot/old.md &&
  printf 'new\n' > agesroot/new.md &&
  touch -t 210001010000 agesroot/new.md
---
# Golden tests: Group by through `/api/tree`

The Files tab’s Group by splits the tree into groups, each a full tree of its members
after the filter (`metabrowser/tree_groups.py`). `/api/tree?group_by=` answers which
groups hold anything, in display order, with their counts and their trees;
`/api/tree?group=<by>:<id>` answers one group’s tree, which is how the browser opens a
folder inside a group.

`groupsroot` holds files of four display groups, all with pinned mtimes, so its trees
are deterministic. `agesroot` holds one old file and one dated in 2100, which is Live
whenever the request runs, since a band admits any mtime newer than its near edge; its
answers are asked at depth 0, so no mtime is printed.

## Test: File type groups, Documentation first, empty groups left out

Archives and Media hold nothing here, so they are not listed.
A Makefile is Code by its name, and Other takes the log file and the extension the
registry does not know.

```console
$ metab groupsroot --api '/api/tree?group_by=type&depth=1'
api: /api/tree?group_by=type&depth=1
status: 200
{
  "root": "<ROOT>",
  "group_by": "type",
  "groups": [
    {
      "id": "docs",
      "label": "Documentation",
      "files": 3,
      "size": 23,
      "entries": 3,
      "tree": [
        {
          "name": "docs",
          "path": "docs",
          "type": "dir",
          "total_files": 1,
          "total_size": 8,
          "mtime": 1700000000.0,
          "has_children": true,
          "children": null
        },
        {
          "name": "README.md",
          "path": "README.md",
          "type": "file",
          "size": 9,
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
      ]
    },
    {
      "id": "code",
      "label": "Code",
      "files": 3,
      "size": 25,
      "entries": 3,
      "tree": [
        {
          "name": "src",
          "path": "src",
          "type": "dir",
          "total_files": 2,
          "total_size": 20,
          "mtime": 1700000000.0,
          "has_children": true,
          "children": null
        },
        {
          "name": "Makefile",
          "path": "Makefile",
          "type": "file",
          "size": 5,
          "mtime": 1700000000.0,
          "ext": ""
        }
      ]
    },
    {
      "id": "data",
      "label": "Data",
      "files": 1,
      "size": 3,
      "entries": 1,
      "tree": [
        {
          "name": "data",
          "path": "data",
          "type": "dir",
          "total_files": 1,
          "total_size": 3,
          "mtime": 1700000000.0,
          "has_children": true,
          "children": null
        }
      ]
    },
    {
      "id": "other",
      "label": "Other",
      "files": 2,
      "size": 15,
      "entries": 2,
      "tree": [
        {
          "name": "logs",
          "path": "logs",
          "type": "dir",
          "total_files": 1,
          "total_size": 8,
          "mtime": 1700000000.0,
          "has_children": true,
          "children": null
        },
        {
          "name": "misc",
          "path": "misc",
          "type": "dir",
          "total_files": 1,
          "total_size": 7,
          "mtime": 1700000000.0,
          "has_children": true,
          "children": null
        }
      ]
    }
  ],
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000
}
? 0
```

## Test: the filter narrows every group, and a group it empties is left out

```console
$ metab groupsroot --api '/api/tree?group_by=type&depth=0&types=.md,.py'
api: /api/tree?group_by=type&depth=0&types=.md,.py
status: 200
{
  "root": "<ROOT>",
  "group_by": "type",
  "groups": [
    {
      "id": "docs",
      "label": "Documentation",
      "files": 2,
      "size": 17,
      "entries": 2,
      "tree": []
    },
    {
      "id": "code",
      "label": "Code",
      "files": 1,
      "size": 9,
      "entries": 1,
      "tree": []
    }
  ],
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000
}
? 0
```

## Test: one group’s tree, as a folder inside it opens

```console
$ metab groupsroot --api '/api/tree?group=type:other&depth=2'
api: /api/tree?group=type:other&depth=2
status: 200
{
  "root": "<ROOT>",
  "tree": [
    {
      "name": "logs",
      "path": "logs",
      "type": "dir",
      "total_files": 1,
      "total_size": 8,
      "mtime": 1700000000.0,
      "has_children": true,
      "children": [
        {
          "name": "run.log",
          "path": "logs/run.log",
          "type": "file",
          "size": 8,
          "mtime": 1700000000.0,
          "ext": ".log"
        }
      ]
    },
    {
      "name": "misc",
      "path": "misc",
      "type": "dir",
      "total_files": 1,
      "total_size": 7,
      "mtime": 1700000000.0,
      "has_children": true,
      "children": [
        {
          "name": "blob.xyz",
          "path": "misc/blob.xyz",
          "type": "file",
          "size": 7,
          "mtime": 1700000000.0,
          "ext": ".xyz"
        }
      ]
    }
  ],
  "filtered": {
    "files": 2,
    "size": 15,
    "entries": 2
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

## Test: Age groups are disjoint bands, with Older for the rest

```console
$ metab agesroot --api '/api/tree?group_by=age&depth=0'
api: /api/tree?group_by=age&depth=0
status: 200
{
  "root": "<ROOT>",
  "group_by": "age",
  "groups": [
    {
      "id": "live",
      "label": "Live",
      "files": 1,
      "size": 4,
      "entries": 1,
      "tree": []
    },
    {
      "id": "older",
      "label": "Older",
      "files": 1,
      "size": 4,
      "entries": 1,
      "tree": []
    }
  ],
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000
}
? 0
```

## Test: a recency filter keeps only the bands inside its window

Past hour holds only what Live does not, and Older is past every window, so only Live is
left.

```console
$ metab agesroot --api '/api/tree?group_by=age&depth=0&recency=1h'
api: /api/tree?group_by=age&depth=0&recency=1h
status: 200
{
  "root": "<ROOT>",
  "group_by": "age",
  "groups": [
    {
      "id": "live",
      "label": "Live",
      "files": 1,
      "size": 4,
      "entries": 1,
      "tree": []
    }
  ],
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
