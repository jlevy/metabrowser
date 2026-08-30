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
