---
sandbox: true
path:
  - ../fixtures/github-pull/no-gh
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "ERROR"
patterns:
  TIMESTAMP: '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'
  APP_HOME: '[^\s"]+/home[a-z-]*'
before: >-
  METABROWSER_CONFIG_DIR="$PWD/config"
  PYTHONPATH="$TRYSCRIPT_TEST_DIR/../.." uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../checkout_replica.py" .
  > fixture.log 2>&1
---
# Golden tests: a store that borrows from a checkout

`tests/checkout_replica.py` builds three homes before these commands run, through the
production CLI path, from a local origin standing in for `https://github.com/octo/demo`.
`home` borrows from `checkout`, named through its linked worktree `feature-x`. Acquiring
one needs a Git the floor admits, so that and everything that fetches is in
`tests/test_cli_checkout_golden.py`, `tests/golden/cli-checkout-overlay.txt`. Reading a
cached store needs no floor.

## Test: a pull request served from an overlay says what it borrows

`borrows` is beside `location`, under the one exception that lets a route name a path of
the reader’s. `shallow` is whether the store’s history stops at a boundary, as the
checkout’s does.

```console
$ metab --cache-dir home --config-dir config https://github.com/octo/demo/pull/1 --api /api/source/status
selection: pull_request
pin: 806ef37f15fef9c34a47873090c6169008db8cd2 (pull request 1 head)
pull_request: 1 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "806ef37f15fef9c34a47873090c6169008db8cd2",
  "ref": "refs/pull/1/head",
  "ref_name": "refs/pull/1/head",
  "name": "demo",
  "origin": "https://github.com/octo/demo",
  "location": "[APP_HOME]/repos/github-com-octo-demo-e7qjzskw2rq/repository.git",
  "borrows": "[CWD]/checkout",
  "shallow": false,
  "refreshable": true,
  "follows": true,
  "latest": "806ef37f15fef9c34a47873090c6169008db8cd2",
  "ref_on_origin": true,
  "last_fetch_at": "2026-09-17T12:00:00Z",
  "last_outcome": {
    "operation": "acquire",
    "outcome": "succeeded",
    "at": "2026-09-17T12:00:00Z"
  },
  "refreshing": false,
  "refresh_quiet": false,
  "stale": true,
  "probe_every_s": null,
  "pull_request": 1,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: the record and the pages read the same as on a full mirror

The store’s refs are only what the origin sent.

```console
$ metab --cache-dir home --config-dir config https://github.com/octo/demo --api '/api/source/refs?kind=branch'
api: /api/source/refs?kind=branch
status: 200
{
  "kind": "branch",
  "query": "",
  "pin": "0b51e0167804d26271bf05e7c4304bfd87d67e01",
  "ref": "refs/remotes/origin/trunk",
  "kinds": [
    "branch",
    "tag"
  ],
  "working_tree": null,
  "origin": null,
  "pull_requests": {
    "state": "absent",
    "complete": false,
    "refreshing": false
  },
  "refs": [
    {
      "name": "trunk",
      "ref": "refs/remotes/origin/trunk",
      "commit": "0b51e0167804d26271bf05e7c4304bfd87d67e01",
      "committed_at": 1577836800.0,
      "default": true,
      "checked_out": false,
      "current": true
    }
  ]
}
? 0
```

```console
$ metab --cache-dir home --config-dir config https://github.com/octo/demo/pull/1 --show p
selection: pull_request
pin: 806ef37f15fef9c34a47873090c6169008db8cd2 (pull request 1 head)
pull_request: 1 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
show: p
route: /view/g1-cA
kind: text
views: source (default)
model: text envelope; size=2 content_bytes=2 content_truncated=False
? 0
```

## Test: the cache routes report the mode and the checkout’s health, and no path

```console
$ metab --cache-dir home --config-dir config root --api /api/cache/stores
api: /api/cache/stores
status: 200
{
  "home": "present",
  "layout_format": "f03",
  "stores": [
    {
      "key": "github-com-octo-demo-e7qjzskw2rq",
      "id": "sha256:65157fba6c20ff9076eace172457003c29579e62f37f276de021d59f37cb9ab4",
      "publication": "published",
      "mode": "overlay",
      "lender": "present",
      "identity": {
        "created_at": "2026-09-17T12:00:00Z",
        "acquisition": {
          "git_version": "2.50.1",
          "object_format": "sha1"
        }
      },
      "state": {
        "default_remote_ref": "refs/remotes/origin/trunk",
        "default_revision": "0b51e0167804d26271bf05e7c4304bfd87d67e01",
        "last_fetch_at": "2026-09-17T12:00:00Z",
        "last_operation": {
          "kind": "acquire",
          "outcome": "succeeded",
          "at": "2026-09-17T12:00:00Z"
        }
      },
      "problems": [],
      "referenced_by": [
        {
          "slug": "github-com-octo-demo-9vhngza0oa1",
          "generation": 1
        }
      ],
      "reference_state": "referenced"
    }
  ],
  "unrecognized_entries": 0,
  "limit": 25,
  "next_after": null
}
? 0
```

## Test: a checkout that has gone is a typed refusal with its repair

Nothing is served, and the recorded path and the command that repairs it are printed.

```console
$ metab --cache-dir home-moved --config-dir config https://github.com/octo/demo/pull/1 --api /api/source/status
Error: the checkout this mirror borrows objects from is gone: [CWD]/other (lender_missing), and this mirror of https://github.com/octo/demo cannot be served without it. If it moved, or another checkout of the repository should lend instead, name it: metab https://github.com/octo/demo --checkout <new path>
? 1
```

The cache routes read records and no object, so they still answer, with
`lender_missing`.

```console
$ metab --cache-dir home-moved --config-dir config root --api /api/cache/stores
api: /api/cache/stores
status: 200
{
  "home": "present",
  "layout_format": "f03",
  "stores": [
    {
      "key": "github-com-octo-demo-e7qjzskw2rq",
      "id": "sha256:65157fba6c20ff9076eace172457003c29579e62f37f276de021d59f37cb9ab4",
      "publication": "published",
      "mode": "overlay",
      "lender": "lender_missing",
      "identity": {
        "created_at": "2026-09-17T12:00:00Z",
        "acquisition": {
          "git_version": "2.50.1",
          "object_format": "sha1"
        }
      },
      "state": {
        "default_remote_ref": "refs/remotes/origin/trunk",
        "default_revision": "0b51e0167804d26271bf05e7c4304bfd87d67e01",
        "last_fetch_at": "2026-09-17T12:00:00Z",
        "last_operation": {
          "kind": "acquire",
          "outcome": "succeeded",
          "at": "2026-09-17T12:00:00Z"
        }
      },
      "problems": [],
      "referenced_by": [
        {
          "slug": "github-com-octo-demo-9vhngza0oa1",
          "generation": 1
        }
      ],
      "reference_state": "referenced"
    }
  ],
  "unrecognized_entries": 0,
  "limit": 25,
  "next_after": null
}
? 0
```

Naming where it is now repairs it, with no network and no floor, and it is remembered.

```console
$ metab --cache-dir home-moved --config-dir config https://github.com/octo/demo/pull/1 --checkout moved --api /api/source/status
borrowing objects from [CWD]/moved
selection: pull_request
pin: 806ef37f15fef9c34a47873090c6169008db8cd2 (pull request 1 head)
pull_request: 1 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "806ef37f15fef9c34a47873090c6169008db8cd2",
  "ref": "refs/pull/1/head",
  "ref_name": "refs/pull/1/head",
  "name": "demo",
  "origin": "https://github.com/octo/demo",
  "location": "[CWD]/home-moved/repos/github-com-octo-demo-e7qjzskw2rq/repository.git",
  "borrows": "[CWD]/moved",
  "shallow": false,
  "refreshable": true,
  "follows": true,
  "latest": "806ef37f15fef9c34a47873090c6169008db8cd2",
  "ref_on_origin": true,
  "last_fetch_at": "2026-09-17T12:00:00Z",
  "last_outcome": {
    "operation": "acquire",
    "outcome": "succeeded",
    "at": "2026-09-17T12:00:00Z"
  },
  "refreshing": false,
  "refresh_quiet": false,
  "stale": true,
  "probe_every_s": null,
  "pull_request": 1,
  "selection_state": null,
  "selection_href": null
}
? 0
```

```console
$ metab --cache-dir home-moved --config-dir config https://github.com/octo/demo/pull/1 --api /api/source/status
selection: pull_request
pin: 806ef37f15fef9c34a47873090c6169008db8cd2 (pull request 1 head)
pull_request: 1 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "806ef37f15fef9c34a47873090c6169008db8cd2",
  "ref": "refs/pull/1/head",
  "ref_name": "refs/pull/1/head",
  "name": "demo",
  "origin": "https://github.com/octo/demo",
  "location": "[CWD]/home-moved/repos/github-com-octo-demo-e7qjzskw2rq/repository.git",
  "borrows": "[CWD]/moved",
  "shallow": false,
  "refreshable": true,
  "follows": true,
  "latest": "806ef37f15fef9c34a47873090c6169008db8cd2",
  "ref_on_origin": true,
  "last_fetch_at": "2026-09-17T12:00:00Z",
  "last_outcome": {
    "operation": "acquire",
    "outcome": "succeeded",
    "at": "2026-09-17T12:00:00Z"
  },
  "refreshing": false,
  "refresh_quiet": false,
  "stale": true,
  "probe_every_s": null,
  "pull_request": 1,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: a merge base the store’s shallow history cannot settle is not guessed

`home-shallow` borrows from a `--depth 3` clone of a merge-heavy history, where Git
alone answers a commit that is not the merge base.
Its fixture allowed no rounds of deepening, as when offline, so the record says
`base_uncertain`, and there is no `comparison` and no `comparison_route`. What the
deepening does is in `tests/golden/cli-checkout-overlay.txt`.

```console
$ metab --cache-dir home-shallow --config-dir config https://github.com/octo/demo/pull/1 --api '/api/plugin/github/pull?number=1'
selection: pull_request
pin: 59f44dac07a12a7c3907fbbcda78e35721c9013b (pull request 1 head)
pull_request: 1 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull?number=1
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 1,
  "pin": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
  "pin_ref": "refs/pull/1/head",
  "fetched_at": "2026-09-17T12:00:00Z",
  "verified_at": "2026-09-17T12:00:00Z",
  "verified_by": "fetch",
  "head_moved": false,
  "checks_pending": true,
  "record_revision": "08db68b486accb2241b515c607e6cd7b6467fb35ecf76f957a802715c2bf4858",
  "fresh_for_s": 60.0,
  "probe_every_s": 5.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "comparison_route": null,
  "image_route": null,
  "rendered_route": null,
  "size_route": null,
  "record": {
    "schema_version": 3,
    "projection_version": 2,
    "source": "https://github.com/octo/demo",
    "number": 1,
    "fetched_at": "2026-09-17T12:00:00Z",
    "reader": "gh:octo-reader",
    "etags": {
      "repos/octo/demo/pulls/1": "W/\"be1470595a6128d72ae596f8a3c82aeaf42e40a434826ed7420b4fd06702aabd\"",
      "repos/octo/demo/issues/1/comments?per_page=100&page=1": "W/\"bd0a3bbed985060704932aa5f94799ce1984041953fa6bceca70fcdfca07da0d\"",
      "repos/octo/demo/pulls/1/reviews?per_page=100&page=1": "W/\"b29824a2b64c489c7be4fce170608fb273df404b41aadcbee5817247f896cc5b\"",
      "repos/octo/demo/pulls/1/comments?per_page=100&page=1": "W/\"5a360c97d34af3baf109ab34e0de37f425d3c28b1ae7494bbe7f24fb075f268b\""
    },
    "pull": {
      "number": 1,
      "title": "Add p",
      "body": "The app counts to one.\r\n\r\nThis teaches it **two**.",
      "body_truncated": false,
      "state": "open",
      "draft": false,
      "merged": false,
      "merged_by": null,
      "merged_by_avatar_url": null,
      "commits": 2,
      "merge_commit_sha": null,
      "labels": [
        {
          "name": "enhancement",
          "color": "2700af",
          "description": "A label's description is its chip's tooltip"
        }
      ],
      "author": "forker",
      "author_avatar_url": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "merged_at": null,
      "closed_at": null,
      "base": {
        "ref": "trunk",
        "sha": "3fe5d55744d3e20e0fdcb2a6c7e774b6d48ea19f",
        "repository": "octo/demo"
      },
      "head": {
        "ref": "pr",
        "sha": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
        "repository": "octo/demo"
      },
      "html_url": "https://github.com/octo/demo/pull/1"
    },
    "issue_comments": [
      {
        "id": 3341937855,
        "author": "maintainer",
        "author_avatar_url": null,
        "body": "Thanks. CI is green; one question inline.",
        "body_truncated": false,
        "created_at": "2026-09-16T17:34:17Z",
        "updated_at": "2026-09-16T17:35:33Z"
      }
    ],
    "reviews": [
      {
        "id": 3274109685,
        "state": "COMMENTED",
        "author": "maintainer",
        "author_avatar_url": null,
        "body": "",
        "body_truncated": false,
        "submitted_at": "2026-09-16T12:32:50Z",
        "commit_id": "df625f09265d214d5f750fed0e37eaf3989dbcc2"
      },
      {
        "id": 3279967139,
        "state": "APPROVED",
        "author": "maintainer",
        "author_avatar_url": null,
        "body": "Looks right.",
        "body_truncated": false,
        "submitted_at": "2026-09-16T17:36:02Z",
        "commit_id": "59f44dac07a12a7c3907fbbcda78e35721c9013b"
      }
    ],
    "review_comments": [
      {
        "id": 2383608906,
        "review_id": 3274109685,
        "in_reply_to": null,
        "path": "src/app.txt",
        "line": null,
        "original_line": 1,
        "start_line": null,
        "original_start_line": null,
        "side": "RIGHT",
        "commit_id": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
        "original_commit_id": "df625f09265d214d5f750fed0e37eaf3989dbcc2",
        "diff_hunk": "@@ -1 +1 @@\n-one\n+one",
        "diff_hunk_truncated": false,
        "author": "maintainer",
        "author_avatar_url": null,
        "body": "Why does this line change?",
        "body_truncated": false,
        "created_at": "2026-09-16T12:32:50Z",
        "updated_at": "2026-09-16T12:32:50Z"
      },
      {
        "id": 2388073350,
        "review_id": 3279967139,
        "in_reply_to": 2383608906,
        "path": "src/app.txt",
        "line": 2,
        "original_line": 2,
        "start_line": null,
        "original_start_line": null,
        "side": "RIGHT",
        "commit_id": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
        "original_commit_id": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
        "diff_hunk": "@@ -1 +1,2 @@\n one\n+two",
        "diff_hunk_truncated": false,
        "author": "forker",
        "author_avatar_url": null,
        "body": "It no longer does; the second line is new.",
        "body_truncated": false,
        "created_at": "2026-09-16T17:30:11Z",
        "updated_at": "2026-09-16T17:30:11Z"
      }
    ],
    "comparison": null,
    "truncated": {
      "issue_comments": false,
      "reviews": false,
      "review_comments": false,
      "text": false
    },
    "unavailable": {
      "comparison": "base_uncertain"
    }
  },
  "core_preview": null,
  "repository_labels": [],
  "labels_pending": false,
  "status": {
    "number": 1,
    "head": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
    "base_ref": "trunk",
    "base": "3fe5d55744d3e20e0fdcb2a6c7e774b6d48ea19f",
    "observed_at": "2026-09-17T12:00:00Z",
    "observed_by": "read",
    "conflicts": "mergeable",
    "merge_state": "blocked",
    "review_decision": "review_required",
    "checks": {
      "state": "pending",
      "counts": {
        "pass": 2,
        "fail": 0,
        "pending": 1,
        "skipping": 0,
        "cancel": 0
      },
      "required_failing": 0,
      "required_pending": 1,
      "listed_at": "2026-09-17T12:00:00Z",
      "moved_at": null
    },
    "auto_merge": {
      "method": "squash",
      "enabled_by": "maintainer",
      "enabled_at": "2026-09-16T17:40:00Z"
    },
    "queue": null
  },
  "readiness": {
    "verdict": "checks_pending",
    "tone": "attention",
    "label": "Checks pending",
    "head": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
    "observed_at": "2026-09-17T12:00:00Z",
    "requirements": [
      {
        "kind": "conflicts",
        "status": "met",
        "summary": "No merge conflicts with trunk.",
        "github_url": null,
        "tone": "success"
      },
      {
        "kind": "checks",
        "status": "waiting",
        "summary": "Some checks are still pending: 2 successful, and 1 pending.",
        "github_url": "https://github.com/octo/demo/pull/1/checks",
        "tone": "attention"
      },
      {
        "kind": "reviews",
        "status": "waiting",
        "summary": "Review required.",
        "github_url": "https://github.com/octo/demo/pull/1",
        "tone": "attention"
      }
    ],
    "auto_merge": {
      "method": "squash",
      "enabled_by": "maintainer",
      "enabled_at": "2026-09-16T17:40:00Z"
    },
    "auto_merge_summary": "Auto-merge enabled (squash)."
  },
  "checks": {
    "number": 1,
    "head": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
    "observed_at": "2026-09-17T12:00:00Z",
    "items": [
      {
        "name": "tests (3.13)",
        "kind": "run",
        "bucket": "pass",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
        "required": true,
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
        "app": "GitHub Actions",
        "description": null
      },
      {
        "name": "docs",
        "kind": "run",
        "bucket": "pending",
        "status": "IN_PROGRESS",
        "conclusion": null,
        "required": true,
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
        "app": "GitHub Actions",
        "description": null
      },
      {
        "name": "docs/readthedocs.org:demo",
        "kind": "status",
        "bucket": "pass",
        "status": null,
        "conclusion": "SUCCESS",
        "required": false,
        "details_url": "https://demo--7.org.readthedocs.build/en/7/",
        "app": null,
        "description": "Read the Docs build succeeded!"
      }
    ],
    "truncated": false
  },
  "status_unavailable": null
}
? 0
```

`shallow` is `true`, since the checkout’s history stops at a boundary.

```console
$ metab --cache-dir home-shallow --config-dir config https://github.com/octo/demo/pull/1 --api /api/source/status
selection: pull_request
pin: 59f44dac07a12a7c3907fbbcda78e35721c9013b (pull request 1 head)
pull_request: 1 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
  "ref": "refs/pull/1/head",
  "ref_name": "refs/pull/1/head",
  "name": "demo",
  "origin": "https://github.com/octo/demo",
  "location": "[CWD]/home-shallow/repos/github-com-octo-demo-e7qjzskw2rq/repository.git",
  "borrows": "[CWD]/shallow",
  "shallow": true,
  "refreshable": true,
  "follows": true,
  "latest": "59f44dac07a12a7c3907fbbcda78e35721c9013b",
  "ref_on_origin": true,
  "last_fetch_at": "2026-09-17T12:00:00Z",
  "last_outcome": {
    "operation": "acquire",
    "outcome": "succeeded",
    "at": "2026-09-17T12:00:00Z"
  },
  "refreshing": false,
  "refresh_quiet": false,
  "stale": true,
  "probe_every_s": null,
  "pull_request": 1,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: an alternates file that disagrees with the record is refused

```console
$ metab --cache-dir home-damaged --config-dir config https://github.com/octo/demo --api /api/source/status
Error: this cached store's record of what it borrows disagrees with its objects/info/alternates file (damaged), so it was not opened. Move the cache directory aside, or set METABROWSER_CACHE_DIR to a different directory
? 1
```

```console
$ metab --cache-dir home-damaged --config-dir config root --api /api/cache/stores
api: /api/cache/stores
status: 200
{
  "home": "present",
  "layout_format": "f03",
  "stores": [
    {
      "key": "github-com-octo-demo-e7qjzskw2rq",
      "id": "sha256:65157fba6c20ff9076eace172457003c29579e62f37f276de021d59f37cb9ab4",
      "publication": "damaged",
      "mode": "overlay",
      "lender": "present",
      "identity": {
        "created_at": "2026-09-17T12:00:00Z",
        "acquisition": {
          "git_version": "2.50.1",
          "object_format": "sha1"
        }
      },
      "state": {
        "default_remote_ref": "refs/remotes/origin/trunk",
        "default_revision": "0b51e0167804d26271bf05e7c4304bfd87d67e01",
        "last_fetch_at": "2026-09-17T12:00:00Z",
        "last_operation": {
          "kind": "acquire",
          "outcome": "succeeded",
          "at": "2026-09-17T12:00:00Z"
        }
      },
      "problems": [
        {
          "record": "store.yml",
          "code": "mismatch",
          "message": "store.yml disagrees with the store's alternates file about what it borrows."
        }
      ],
      "referenced_by": [
        {
          "slug": "github-com-octo-demo-9vhngza0oa1",
          "generation": 1
        }
      ],
      "reference_state": "referenced"
    }
  ],
  "unrecognized_entries": 0,
  "limit": 25,
  "next_after": null
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
