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
  mkdir -p gitroot/src &&
  cd gitroot &&
  git init -q --initial-branch=main . &&
  printf '# Title\n' > README.md &&
  printf 'x = 1\n' > src/app.py &&
  printf 'note\n' > notes.txt &&
  git add -A &&
  git commit -q -m 'base' &&
  printf '# Title\n\nMore.\n' > README.md &&
  printf 'x = 2\n' > src/app.py &&
  git mv notes.txt notes.md &&
  printf '\211PNG\r\n\032\n\000' > logo.png &&
  git add -A &&
  git commit -q -m 'docs, code, a rename across types, and a binary file'
---
# Golden tests: a comparison narrowed by file type

`&types=` on `/api/plugin/diff/comparison` keeps the changed files of the chosen types,
in the File type filter’s vocabulary: a dotted token is a logical extension and a bare
one a whole filename.
The diff view’s File type chooser asks for this answer, and the pull request comparison
route reads the same parameter through `comparison_at`.

A change is of a type when either of its sides is, so the rename of `notes.txt` to
`notes.md` is kept by `.md` and by `.txt`. The kept files’ totals are the answer’s
totals, and the hydration bound counts only kept files.

The fixture pins identity and dates, so the commit IDs below are the same on every
machine.

## Test: `.md` keeps the edited Markdown file and the rename into Markdown

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&types=.md'
api: /api/plugin/diff/comparison?revision=HEAD&types=.md
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:bd4f1215f4c76ca6",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "fd217d55d87588aa9177b86fdeb9f8f9554f3752",
      "symbolic": "HEAD"
    },
    "right": {
      "kind": "commit",
      "id": "92226fd2673bc1098681206bb910a802320759d6"
    },
    "options": {
      "context": 3,
      "rename_detection": true,
      "rename_similarity": 50
    },
    "warnings": []
  },
  "manifest": {
    "files": [
      {
        "id": "f1",
        "kind": "modified",
        "old": {
          "path": "README.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "a9738745554a034f4e28b7eaa04a6ce09e294b36"
          }
        },
        "new": {
          "path": "README.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "7f52fb1723524f5c8ed7644ef1c1c27af93acdf6"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 2,
        "deletions": 0
      },
      {
        "id": "f3",
        "kind": "renamed",
        "old": {
          "path": "notes.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "519dd581e50e5b45d3b3c76c3172e9c3ec293488"
          }
        },
        "new": {
          "path": "notes.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "519dd581e50e5b45d3b3c76c3172e9c3ec293488"
          }
        },
        "similarity": 100,
        "binary": false,
        "availability": "ready",
        "additions": 0,
        "deletions": 0
      }
    ],
    "totals": {
      "files": 2,
      "additions": 2,
      "deletions": 0,
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
          "new_count": 3,
          "lines": [
            {
              "op": "context",
              "text": "# Title",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "More.",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f3": {
      "file_id": "f3",
      "hunks": [],
      "truncated": false
    }
  }
}
? 0
```

## Test: `.txt` keeps the rename out of plain text, by its old side

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&types=.txt'
api: /api/plugin/diff/comparison?revision=HEAD&types=.txt
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:bd4f1215f4c76ca6",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "fd217d55d87588aa9177b86fdeb9f8f9554f3752",
      "symbolic": "HEAD"
    },
    "right": {
      "kind": "commit",
      "id": "92226fd2673bc1098681206bb910a802320759d6"
    },
    "options": {
      "context": 3,
      "rename_detection": true,
      "rename_similarity": 50
    },
    "warnings": []
  },
  "manifest": {
    "files": [
      {
        "id": "f3",
        "kind": "renamed",
        "old": {
          "path": "notes.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "519dd581e50e5b45d3b3c76c3172e9c3ec293488"
          }
        },
        "new": {
          "path": "notes.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "519dd581e50e5b45d3b3c76c3172e9c3ec293488"
          }
        },
        "similarity": 100,
        "binary": false,
        "availability": "ready",
        "additions": 0,
        "deletions": 0
      }
    ],
    "totals": {
      "files": 1,
      "additions": 0,
      "deletions": 0,
      "exact": true
    },
    "truncated": false
  },
  "patches": {
    "f3": {
      "file_id": "f3",
      "hunks": [],
      "truncated": false
    }
  }
}
? 0
```

## Test: repeated and comma-separated tokens are one selection

Case folds, and a token named twice is named once.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&types=.PY,.png&types=.py'
api: /api/plugin/diff/comparison?revision=HEAD&types=.PY,.png&types=.py
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:bd4f1215f4c76ca6",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "fd217d55d87588aa9177b86fdeb9f8f9554f3752",
      "symbolic": "HEAD"
    },
    "right": {
      "kind": "commit",
      "id": "92226fd2673bc1098681206bb910a802320759d6"
    },
    "options": {
      "context": 3,
      "rename_detection": true,
      "rename_similarity": 50
    },
    "warnings": []
  },
  "manifest": {
    "files": [
      {
        "id": "f2",
        "kind": "added",
        "new": {
          "path": "logo.png",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "aa860abb474c16b64e6a58a44d70206090fc2c56"
          }
        },
        "binary": true,
        "availability": "binary",
        "additions": null,
        "deletions": null
      },
      {
        "id": "f4",
        "kind": "modified",
        "old": {
          "path": "src/app.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "7d4290a117a4ddcc11daae7ea675841033830c8f"
          }
        },
        "new": {
          "path": "src/app.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "407de3068e7b5950585d5abed9776d104235a85d"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 1
      }
    ],
    "totals": {
      "files": 2,
      "additions": 1,
      "deletions": 1,
      "exact": true
    },
    "truncated": false
  },
  "patches": {
    "f4": {
      "file_id": "f4",
      "hunks": [
        {
          "old_start": 1,
          "old_count": 1,
          "new_start": 1,
          "new_count": 1,
          "lines": [
            {
              "op": "del",
              "text": "x = 1",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "x = 2",
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

## Test: a type the change set has none of answers an empty, valid document

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&types=.rs'
api: /api/plugin/diff/comparison?revision=HEAD&types=.rs
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:bd4f1215f4c76ca6",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "fd217d55d87588aa9177b86fdeb9f8f9554f3752",
      "symbolic": "HEAD"
    },
    "right": {
      "kind": "commit",
      "id": "92226fd2673bc1098681206bb910a802320759d6"
    },
    "options": {
      "context": 3,
      "rename_detection": true,
      "rename_similarity": 50
    },
    "warnings": []
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

## Test: a deferred file’s own request is narrowed too

The view asks for one file with the same parameters it asked for the list with.
A file the selection does not keep is not in that answer.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&types=.md&file=src/app.py'
api: /api/plugin/diff/comparison?revision=HEAD&types=.md&file=src/app.py
status: 404
{
  "error": "diff_comparison",
  "message": "This comparison has no entry for that path.",
  "path": "src/app.py"
}
Error: /api/plugin/diff/comparison?revision=HEAD&types=.md&file=src/app.py returned HTTP 404
? 1
```

## Test: `group=type:docs` keeps the change set’s documents

`&group=type:<id>` keeps the changed files in one File type group, as the Files tab’s
Group by places them, either side counting.
A pull request’s Docs tab asks for `type:docs`: here the edited `README.md` and the
rename of `notes.txt` to `notes.md`, and not the Python file or the image.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&group=type:docs' > docs.json
? 0
```

```console
$ grep -E '^status|"path"|"files"|"truncated"' docs.json
status: 200
    "files": [
          "path": "README.md",
          "path": "README.md",
          "path": "notes.txt",
          "path": "notes.md",
      "files": 2,
    "truncated": false
      "truncated": false
      "truncated": false
? 0
```

## Test: a group that is no File type group is refused

A comparison’s files have no ages, so only a `type:` group narrows one.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&group=age:live'
api: /api/plugin/diff/comparison?revision=HEAD&group=age:live
status: 400
{
  "error": "diff_comparison",
  "message": "group is a File type group, type:<id>.",
  "path": "HEAD"
}
Error: /api/plugin/diff/comparison?revision=HEAD&group=age:live returned HTTP 400
? 1
```

## Test: `view=types` answers the comparison’s File type counts

The rows the Files tab’s File type menu reads, over every listed change: the diff view’s
menu lists only the types its comparison has, with these counts.
A change counts once under each type either side has, so the rename counts under `.md`
and `.txt`. Neither side of a comparison has gitignored files, so the third column is 0.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&view=types'
api: /api/plugin/diff/comparison?revision=HEAD&view=types
status: 200
{
  "comparison_id": "git:bd4f1215f4c76ca6",
  "files": 4,
  "truncated": false,
  "extensions": [
    [
      ".md",
      2,
      0
    ],
    [
      ".png",
      1,
      0
    ],
    [
      ".py",
      1,
      0
    ],
    [
      ".txt",
      1,
      0
    ]
  ],
  "canonical_extensions": [
    [
      ".md",
      2,
      0
    ],
    [
      ".png",
      1,
      0
    ],
    [
      ".py",
      1,
      0
    ],
    [
      ".txt",
      1,
      0
    ]
  ],
  "type_families": [
    [
      "markdown",
      2,
      0
    ],
    [
      "images",
      1,
      0
    ],
    [
      "plain-text",
      1,
      0
    ],
    [
      "python",
      1,
      0
    ]
  ],
  "type_presets": [
    [
      "docs",
      2,
      0
    ],
    [
      "code",
      1,
      0
    ],
    [
      "data",
      0,
      0
    ],
    [
      "archives",
      0,
      0
    ],
    [
      "media",
      1,
      0
    ]
  ]
}
? 0
```

## Test: the counts do not narrow with the selection

The menu keeps every type while the reader narrows, so `types=` and `file=` change
nothing here: the answer below its address line is the whole comparison’s.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&view=types' > whole.txt
? 0
```

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&view=types&types=.md&file=README.md' > narrowed.txt
? 0
```

```console
$ tail -n +2 whole.txt > whole-body.txt && tail -n +2 narrowed.txt | cmp - whole-body.txt && echo same
same
? 0
```

## Test: an unknown view is refused

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&view=tally'
api: /api/plugin/diff/comparison?revision=HEAD&view=tally
status: 400
{
  "error": "diff_comparison",
  "message": "view is types, or absent for the comparison itself.",
  "path": "HEAD"
}
Error: /api/plugin/diff/comparison?revision=HEAD&view=tally returned HTTP 400
? 1
```
