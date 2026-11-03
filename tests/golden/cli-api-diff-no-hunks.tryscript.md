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
  mkdir -p gitroot/pkg patchroot &&
  cd gitroot &&
  git init -q --initial-branch=main . &&
  printf 'old\n' > kept.txt &&
  : > pkg/__init__.py &&
  printf '\000\001\002' > logo.bin &&
  git add -A &&
  git commit -q -m 'base' &&
  git tag base &&
  printf 'new\n' > kept.txt &&
  rm pkg/__init__.py logo.bin &&
  git add -A &&
  git commit -q -m 'delete an empty file and a binary one' &&
  git tag target &&
  cd ../patchroot &&
  printf -- 'diff --git a/kept.txt b/kept.txt\n--- a/kept.txt\n+++ b/kept.txt\n@@ -1 +1 @@\n-old\n+new\ndiff --git a/empty-gone.txt b/empty-gone.txt\ndeleted file mode 100644\nindex e69de29..0000000\ndiff --git a/empty-new.txt b/empty-new.txt\nnew file mode 100644\nindex 0000000..e69de29\ndiff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\ndiff --git a/was.txt b/now.txt\nsimilarity index 100%%\nrename from was.txt\nrename to now.txt\n' > sections.patch
---
# Golden tests: changes with no lines to show

Git writes no `---`, `+++` or `@@` for a change with no lines: an empty file deleted or
added, a binary file deleted, a mode change, a rename of identical content.
The `diff --git` line and the extended headers are all such a section says.
The parser once could not model a deleted file with no hunks, and threw the document
away when any section failed, so a pull request deleting an empty `__init__.py` had no
Files changed at all.

The fixture pins identity and dates, so the commit IDs below are the same on every
machine.

## Test: a patch file keeps every such section

```console
$ metab patchroot --api '/api/plugin/diff/children?path=sections.patch'
api: /api/plugin/diff/children?path=sections.patch
status: 200
{
  "children": [
    {
      "name": "kept.txt",
      "path": "sections.patch/kept.txt",
      "badge": "M"
    },
    {
      "name": "empty-gone.txt",
      "path": "sections.patch/empty-gone.txt",
      "badge": "D"
    },
    {
      "name": "empty-new.txt",
      "path": "sections.patch/empty-new.txt",
      "badge": "A"
    },
    {
      "name": "run.sh",
      "path": "sections.patch/run.sh",
      "badge": "M"
    },
    {
      "name": "now.txt",
      "path": "sections.patch/now.txt",
      "badge": "R"
    }
  ],
  "truncated": false
}
? 0
```

## Test: a comparison deleting an empty file and a binary file has its files

```console
$ metab gitroot --api '/api/plugin/diff/comparison?left=base&right=target&base_policy=merge_base'
api: /api/plugin/diff/comparison?left=base&right=target&base_policy=merge_base
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:69421d61d9bc6fcd",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "merge_base",
    "left": {
      "kind": "commit",
      "id": "66b6bcab7243aacf3df1984510223749bccb6f57",
      "symbolic": "base"
    },
    "right": {
      "kind": "commit",
      "id": "d55441c046919721632c74099fe0fd001787ca00",
      "symbolic": "target"
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
          "path": "kept.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "3367afdbbf91e638efe983616377c60477cc6612"
          }
        },
        "new": {
          "path": "kept.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "3e757656cf36eca53338e520d134963a44f793f8"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 1
      },
      {
        "id": "f2",
        "kind": "deleted",
        "old": {
          "path": "logo.bin",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "8352675d67aed6625ece79af41c27fdb4ee2e867"
          }
        },
        "binary": true,
        "availability": "binary",
        "additions": null,
        "deletions": null
      },
      {
        "id": "f3",
        "kind": "deleted",
        "old": {
          "path": "pkg/__init__.py",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 0,
        "deletions": 0
      }
    ],
    "totals": {
      "files": 3,
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
