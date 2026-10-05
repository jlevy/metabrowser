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
patterns:
  APP_HOME: '[^\s"]+/home'
  STORE_KEY: '[0-9a-f]{64}'
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
name the two commits, and each change’s `old` and `new` name the path at each and say
what kind of entry it is.
A side the change does not have is absent, so a deleted file has no `new` and an added
file no `old`, and a renamed file’s `old` is its old path.

`tests/diff_view_file_fixture.py` writes a bare `origin.git` with `git fast-import`, so
every commit ID below is the same on every machine: `trunk` is `first` (`a5232ab…`) then
`second` (`6ac4c8b…`), and `base` (`0dcf612…`) branches from `first`. `changesroot` is a
clone of it without a checkout, and `home` is an application home that acquired it.
The comparison of a whole commit, and the one from a merge base that a pull request’s
Files changed is, are long documents, pinned once and in full in
`tests/fixtures/diff-view-file-responses.json`, which
`tests/test_diff_view_file_session.py` checks against the server.
`tests/golden/cli-ui-diff-view-file.tryscript.md` shows what View file offers for each
change in them: a name that is not UTF-8, a symbolic link, a submodule, and the merge
base a base side opens at.
The commands here are the two a transcript can show whole: one change of that commit,
and the switch to its parent.

## Test: a renamed file’s old side is its old path at the parent

`&file=` narrows the comparison to one change.
`resolved.left` is the parent and `resolved.right` the commit.

```console
$ metab changesroot --api '/api/plugin/diff/comparison?revision=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&file=src/new_name.py'
api: /api/plugin/diff/comparison?revision=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&file=src/new_name.py
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:314b52cd65f62d3a",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "a5232ab93056074aa3dd87c7b3c28ca84081a6a0",
      "symbolic": "6ac4c8b5eb94eecbdb621d629b31066f050c75f1"
    },
    "right": {
      "kind": "commit",
      "id": "6ac4c8b5eb94eecbdb621d629b31066f050c75f1"
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
        "id": "f6",
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
      "files": 1,
      "additions": 0,
      "deletions": 0,
      "exact": true
    },
    "truncated": false
  },
  "patches": {
    "f6": {
      "file_id": "f6",
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
{"oid": "a5232ab93056074aa3dd87c7b3c28ca84081a6a0", "view": "/view/g1-c3Jj/g1-b2xkX25hbWUucHk"}
? 0
```

The answer’s `view_href` is that address, because the parent has the file.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-parent.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "a5232ab93056074aa3dd87c7b3c28ca84081a6a0",
    "ref": null,
    "ref_name": null,
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/repository-stores/[STORE_KEY]/repository.git",
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
