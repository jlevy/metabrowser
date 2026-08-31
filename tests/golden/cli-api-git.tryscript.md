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
  mkdir -p gitroot &&
  cd gitroot &&
  git init -q --initial-branch=main . &&
  printf '# Repo\n' > README.md &&
  git add README.md &&
  git commit -q -m 'first commit' &&
  printf 'more\n' >> README.md &&
  printf 'x\n' > other.txt &&
  git add -A &&
  git commit -q -m 'second commit' &&
  git tag v1
---
# Golden tests: the Git routes through `--api`

The whole Git panel reads these five routes, and none of them had a transcript.

The fixture pins author and committer identity and dates, and `GIT_CONFIG_GLOBAL` and
`GIT_CONFIG_SYSTEM` point at `/dev/null` so no developer configuration leaks in.
A commit hash is a function of its tree, parents, identity, dates, and message and
nothing else, so the revisions below are **identical on every machine and every run** —
which is why they are asserted literally rather than hidden behind a pattern.

`--initial-branch=main` is required: the default branch name varies by Git version and
is the one genuinely unstable thing in the recipe.

## Test: repository identity and HEAD

```console
$ metab gitroot --api /api/git/repo
api: /api/git/repo
status: 200
{
  "is_repo": true,
  "root": "",
  "head": {
    "ref": "refs/heads/main",
    "revision": "703de1c4a3360d55e60646f300ceb6c926377221",
    "detached": false,
    "unborn": false
  }
}
? 0
```

## Test: refs, with the branch and the tag

```console
$ metab gitroot --api /api/git/refs
api: /api/git/refs
status: 200
{
  "is_repo": true,
  "refs": [
    {
      "id": "refs/heads/main",
      "name": "main",
      "kind": "branch",
      "revision": "703de1c4a3360d55e60646f300ceb6c926377221",
      "is_head": true
    },
    {
      "id": "refs/tags/v1",
      "name": "v1",
      "kind": "tag",
      "revision": "703de1c4a3360d55e60646f300ceb6c926377221"
    }
  ]
}
? 0
```

## Test: history summary

```console
$ metab gitroot --api /api/git/summary
api: /api/git/summary
status: 200
{
  "is_repo": true,
  "commit_count": 2,
  "first_commit_at": 1577836800.0
}
? 0
```

## Test: a log page

`page_cursor` normalizes to `<CURSOR>`: it carries a per-request random session token,
so unlike the revisions it cannot be pinned by any fixture.

```console
$ metab gitroot --api '/api/git/log?limit=2'
api: /api/git/log?limit=2
status: 200
{
  "is_repo": true,
  "commits": [
    {
      "id": "703de1c4a3360d55e60646f300ceb6c926377221",
      "short_id": "703de1c",
      "parent_ids": [
        "6b7e50c374caae27f9758a6a8b1bccdc6d50ec11"
      ],
      "author": {
        "name": "Test",
        "email": "test@example.com"
      },
      "authored_at": 1577836800.0,
      "committed_at": 1577836800.0,
      "subject": "second commit",
      "refs": [
        {
          "id": "refs/heads/main",
          "name": "main",
          "kind": "branch",
          "revision": "703de1c4a3360d55e60646f300ceb6c926377221",
          "is_head": true,
          "is_trunk": true
        },
        {
          "id": "refs/tags/v1",
          "name": "v1",
          "kind": "tag",
          "revision": "703de1c4a3360d55e60646f300ceb6c926377221"
        }
      ]
    },
    {
      "id": "6b7e50c374caae27f9758a6a8b1bccdc6d50ec11",
      "short_id": "6b7e50c",
      "parent_ids": [],
      "author": {
        "name": "Test",
        "email": "test@example.com"
      },
      "authored_at": 1577836800.0,
      "committed_at": 1577836800.0,
      "subject": "first commit"
    }
  ],
  "cursor": null,
  "has_more": false,
  "page": 0,
  "page_cursor": "<CURSOR>",
  "previous_cursor": null,
  "scope": "default",
  "scope_refs": [
    "HEAD",
    "main"
  ],
  "scope_fingerprint": "2d332d88aed1e144d31b329ef329e119064e86557a5f3bedd389d6e58e04e2aa",
  "graph_checkpoint": {
    "version": 1,
    "prior_swimlanes": [],
    "color_index": -1,
    "head_revision": "703de1c4a3360d55e60646f300ceb6c926377221",
    "scope_fingerprint": "2d332d88aed1e144d31b329ef329e119064e86557a5f3bedd389d6e58e04e2aa"
  }
}
? 0
```

## Test: one commit’s detail and file changes

```console
$ metab gitroot --api /api/git/commit/703de1c4a3360d55e60646f300ceb6c926377221
api: /api/git/commit/703de1c4a3360d55e60646f300ceb6c926377221
status: 200
{
  "is_repo": true,
  "commit": {
    "id": "703de1c4a3360d55e60646f300ceb6c926377221",
    "short_id": "703de1c",
    "parent_ids": [
      "6b7e50c374caae27f9758a6a8b1bccdc6d50ec11"
    ],
    "author": {
      "name": "Test",
      "email": "test@example.com"
    },
    "authored_at": 1577836800.0,
    "committed_at": 1577836800.0,
    "subject": "second commit"
  },
  "body": "",
  "stats": {
    "files_changed": 2,
    "files_modified": 1,
    "files_added": 1,
    "files_deleted": 0,
    "additions": 2,
    "deletions": 0
  },
  "files": [
    {
      "path": "README.md",
      "status": "modified",
      "additions": 1,
      "deletions": 0
    },
    {
      "path": "other.txt",
      "status": "added",
      "additions": 1,
      "deletions": 0
    }
  ],
  "files_truncated": false
}
? 0
```

## Test: an unknown revision is reported honestly

```console
$ metab gitroot --api /api/git/commit/0000000000000000000000000000000000000000
api: /api/git/commit/0000000000000000000000000000000000000000
status: 404
{
  "error": "unknown revision"
}
Error: /api/git/commit/0000000000000000000000000000000000000000 returned HTTP 404
? 1
```

## Test: the comparison hook resolves a revision

`cli-api-plugins` pins this hook’s refusal when neither endpoint is named.
The resolved form needs a repository, so it lives here: the manifest reports the two
changed files and the patches carry their hunks.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=703de1c4a3360d55e60646f300ceb6c926377221'
api: /api/plugin/diff/comparison?revision=703de1c4a3360d55e60646f300ceb6c926377221
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:6af1e10278161613",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "first_parent",
    "left": {
      "kind": "commit",
      "id": "6b7e50c374caae27f9758a6a8b1bccdc6d50ec11",
      "symbolic": "703de1c4a3360d55e60646f300ceb6c926377221"
    },
    "right": {
      "kind": "commit",
      "id": "703de1c4a3360d55e60646f300ceb6c926377221"
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
            "oid": "f8051e05d7cc77b9aaeef09bc92709cfdead7d6d"
          }
        },
        "new": {
          "path": "README.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "6c3860949c1b22ea0adb00e5386b2baf83188790"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 0
      },
      {
        "id": "f2",
        "kind": "added",
        "new": {
          "path": "other.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "587be6b4c3f93f93c489c0111bba5596147a26cb"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
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
          "new_count": 2,
          "lines": [
            {
              "op": "context",
              "text": "# Repo",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "more",
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
              "text": "x",
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

## Test: `--show` resolves a commit route

`/commit/<rev>` and `/commit/<rev>/<inner>` are browser addresses, not API routes.
This is their first end-to-end coverage: the grammar decodes, the comparison resolves,
and the views come from the same registry `/api/file` reads.

```console
$ metab gitroot --show /commit/703de1c4a3360d55e60646f300ceb6c926377221
show: /commit/703de1c4a3360d55e60646f300ceb6c926377221
route: /commit/703de1c4a3360d55e60646f300ceb6c926377221
kind: comparison
views: diff (default)
model: comparison envelope; comparison_id=git:6af1e10278161613 kind=content base_policy=first_parent files=2 truncated=False
? 0
```

## Test: `--show` resolves one file inside a commit

```console
$ metab gitroot --show /commit/703de1c4a3360d55e60646f300ceb6c926377221/README.md
show: /commit/703de1c4a3360d55e60646f300ceb6c926377221/README.md
route: /commit/703de1c4a3360d55e60646f300ceb6c926377221/README.md
kind: comparison
views: diff (default)
model: comparison envelope; comparison_id=git:6af1e10278161613 kind=content base_policy=first_parent files=1 truncated=False file=README.md
? 0
```

## Test: a malformed revision is refused by the grammar

```console
$ metab gitroot --show '/commit/not-a-revision!'
Error: /commit/not-a-revision! is not a route this grammar accepts
? 1
```
