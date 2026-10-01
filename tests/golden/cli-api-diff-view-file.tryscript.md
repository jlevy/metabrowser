---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "ERROR"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  PYTHONPATH="$TRYSCRIPT_TEST_DIR/../.."
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python -m tests.diff_view_file_fixture .
  > fixture.log 2>&1 &&
  git clone -q --no-checkout origin.git changesroot
---
# Golden tests: the sides of a changed file, and where each opens

View file on a diff’s file bar opens a changed file at either side of the comparison.
What it needs is all in the comparison document: `resolved.left` and `resolved.right`
name the two commits, and each change’s `old` and `new` name the path at each.
A side the change does not have is absent, so a deleted file has no `new` and an added
file no `old`, and a renamed file’s `old` is its old path.

`tests/diff_view_file_fixture.py` writes a bare `origin.git` with `git fast-import`, so
every commit ID below is the same on every machine: `trunk` is `first` (`fb85257…`) then
`second` (`037ec68…`), which modifies `README.md`, adds `added.txt`, deletes `gone.txt`,
renames `src/old_name.py` to `src/new_name.py`, and modifies a file whose name holds the
Latin-1 byte for `é`, which is not UTF-8; `base` (`449e11d…`) branches from `first`.
`changesroot` is a clone of it without a checkout, and `home` is an application home
that acquired it.

## Test: a commit’s comparison names the parent, the commit, and each side’s path

A name that is not UTF-8 shows replacement characters in `path` and carries its bytes in
`path_b64`, which is what its `/view/` address is built from.

```console
$ metab changesroot --api '/api/plugin/diff/comparison?revision=037ec682a66fd0c1b7a318237ecd6b386147a32d'
api: /api/plugin/diff/comparison?revision=037ec682a66fd0c1b7a318237ecd6b386147a32d
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:138c69b75751026f",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "fb85257e8b1271d607ef49d7d4246fd2ad2484e6",
      "symbolic": "037ec682a66fd0c1b7a318237ecd6b386147a32d"
    },
    "right": {
      "kind": "commit",
      "id": "037ec682a66fd0c1b7a318237ecd6b386147a32d"
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
            "oid": "11ef693690b79c92f3bc49c28af42395e7c5e131"
          }
        },
        "new": {
          "path": "README.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "fd873d671e05f4044eba6e6caa29844caf26971f"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 2,
        "deletions": 1
      },
      {
        "id": "f2",
        "kind": "added",
        "new": {
          "path": "added.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "fa49b077972391ad58037050f2a75f74e3671e92"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 0
      },
      {
        "id": "f3",
        "kind": "deleted",
        "old": {
          "path": "gone.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "3d3f93392e84a20160817a9c597490e4753c4420"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 0,
        "deletions": 1
      },
      {
        "id": "f4",
        "kind": "modified",
        "old": {
          "path": "latin1-�.txt",
          "path_b64": "bGF0aW4xLekudHh0",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "117429733fa72e52444bf313a05756fc321b9d9b"
          }
        },
        "new": {
          "path": "latin1-�.txt",
          "path_b64": "bGF0aW4xLekudHh0",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "55aa3f973017187f9a4068311ea98c137af4dd5a"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 1
      },
      {
        "id": "f5",
        "kind": "renamed",
        "old": {
          "path": "src/old_name.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "78495b268f6b1ac51adbd86a48d867cb876d18f6"
          }
        },
        "new": {
          "path": "src/new_name.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "78495b268f6b1ac51adbd86a48d867cb876d18f6"
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
      "files": 5,
      "additions": 4,
      "deletions": 3,
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
          "old_count": 3,
          "new_start": 1,
          "new_count": 4,
          "lines": [
            {
              "op": "context",
              "text": "# Changes",
              "no_newline": false
            },
            {
              "op": "context",
              "text": "",
              "no_newline": false
            },
            {
              "op": "del",
              "text": "First line.",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "First line, changed.",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "Second line.",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f2": {
      "file_id": "f2",
      "hunks": [
        {
          "old_start": 0,
          "old_count": 0,
          "new_start": 1,
          "new_count": 1,
          "lines": [
            {
              "op": "add",
              "text": "new file",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f3": {
      "file_id": "f3",
      "hunks": [
        {
          "old_start": 1,
          "old_count": 1,
          "new_start": 0,
          "new_count": 0,
          "lines": [
            {
              "op": "del",
              "text": "gone soon",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
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
              "text": "a Latin-1 name",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "a Latin-1 name, edited",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f5": {
      "file_id": "f5",
      "hunks": [],
      "truncated": false
    }
  }
}
? 0
```

## Test: a comparison from a merge base names the merge base, not the base’s tip

A pull request’s Files changed is this comparison, of its base and its head.
`resolved.left` is `first`, their merge base, so that is the commit the base side of a
file opens at.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api '/api/plugin/diff/comparison?left=449e11d3cdd15a48bb472b9cc978995758946f5f&right=037ec682a66fd0c1b7a318237ecd6b386147a32d&base_policy=merge_base'
api: /api/plugin/diff/comparison?left=449e11d3cdd15a48bb472b9cc978995758946f5f&right=037ec682a66fd0c1b7a318237ecd6b386147a32d&base_policy=merge_base
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:138c69b75751026f",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "merge_base",
    "left": {
      "kind": "commit",
      "id": "fb85257e8b1271d607ef49d7d4246fd2ad2484e6",
      "symbolic": "449e11d3cdd15a48bb472b9cc978995758946f5f"
    },
    "right": {
      "kind": "commit",
      "id": "037ec682a66fd0c1b7a318237ecd6b386147a32d",
      "symbolic": "037ec682a66fd0c1b7a318237ecd6b386147a32d"
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
            "oid": "11ef693690b79c92f3bc49c28af42395e7c5e131"
          }
        },
        "new": {
          "path": "README.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "fd873d671e05f4044eba6e6caa29844caf26971f"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 2,
        "deletions": 1
      },
      {
        "id": "f2",
        "kind": "added",
        "new": {
          "path": "added.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "fa49b077972391ad58037050f2a75f74e3671e92"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 0
      },
      {
        "id": "f3",
        "kind": "deleted",
        "old": {
          "path": "gone.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "3d3f93392e84a20160817a9c597490e4753c4420"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 0,
        "deletions": 1
      },
      {
        "id": "f4",
        "kind": "modified",
        "old": {
          "path": "latin1-�.txt",
          "path_b64": "bGF0aW4xLekudHh0",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "117429733fa72e52444bf313a05756fc321b9d9b"
          }
        },
        "new": {
          "path": "latin1-�.txt",
          "path_b64": "bGF0aW4xLekudHh0",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "55aa3f973017187f9a4068311ea98c137af4dd5a"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 1
      },
      {
        "id": "f5",
        "kind": "renamed",
        "old": {
          "path": "src/old_name.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "78495b268f6b1ac51adbd86a48d867cb876d18f6"
          }
        },
        "new": {
          "path": "src/new_name.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "78495b268f6b1ac51adbd86a48d867cb876d18f6"
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
      "files": 5,
      "additions": 4,
      "deletions": 3,
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
          "old_count": 3,
          "new_start": 1,
          "new_count": 4,
          "lines": [
            {
              "op": "context",
              "text": "# Changes",
              "no_newline": false
            },
            {
              "op": "context",
              "text": "",
              "no_newline": false
            },
            {
              "op": "del",
              "text": "First line.",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "First line, changed.",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "Second line.",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f2": {
      "file_id": "f2",
      "hunks": [
        {
          "old_start": 0,
          "old_count": 0,
          "new_start": 1,
          "new_count": 1,
          "lines": [
            {
              "op": "add",
              "text": "new file",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f3": {
      "file_id": "f3",
      "hunks": [
        {
          "old_start": 1,
          "old_count": 1,
          "new_start": 0,
          "new_count": 0,
          "lines": [
            {
              "op": "del",
              "text": "gone soon",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
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
              "text": "a Latin-1 name",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "a Latin-1 name, edited",
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    "f5": {
      "file_id": "f5",
      "hunks": [],
      "truncated": false
    }
  }
}
? 0
```

## Test: switching to the parent answers where the old path opens

`pin-parent.json` is what View file posts for the renamed file’s old side: the parent
commit, and the `/view/` address of `src/old_name.py`.

```console
$ cat pin-parent.json
{"oid": "fb85257e8b1271d607ef49d7d4246fd2ad2484e6", "view": "/view/g1-c3Jj/g1-b2xkX25hbWUucHk"}
? 0
```

The answer’s `view_href` is that address, because the parent has the file.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-parent.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "fb85257e8b1271d607ef49d7d4246fd2ad2484e6",
    "ref": null,
    "ref_name": null,
    "refreshable": true,
    "latest": null,
    "ref_on_origin": null,
    "last_fetch_at": "2026-09-17T12:00:05Z",
    "last_outcome": {
      "operation": "acquire",
      "outcome": "succeeded",
      "at": "2026-09-17T12:00:05Z"
    },
    "refreshing": false,
    "stale": true,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  },
  "view_href": "/view/g1-c3Jj/g1-b2xkX25hbWUucHk"
}
? 0
```
