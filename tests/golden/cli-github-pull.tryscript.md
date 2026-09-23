---
sandbox: true
path:
  - ../fixtures/github-pull/no-gh
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" .
  > fixture.log 2>&1
---
# Golden tests: pull-request data from the cache

`tests/github_pull_fixture.py` builds `home` before these commands run: a mirror of
`https://github.com/octo/demo`, fetched from a local origin that carries GitHub’s
`refs/pull/<n>/head`, and the records of four pull requests, each fetched once through
`metab <pr-url> --no-serve` with a fake `gh` replaying scrubbed real responses and a
clock fixed at 2026-09-17T12:00:00Z.

| PR | Shape |
| --- | --- |
| 7 | open, from a fork whose commits only `refs/pull/7/head` reaches |
| 8 | merged into `topic` |
| 9 | closed, its fork deleted, its `base.sha` on no mirrored ref |
| 10 | open draft |

Every command below answers from that cache and none reaches the network or needs a Git
the acquisition floor admits.
`gh` is `tests/fixtures/github-pull/no-gh/gh`, which fails every command: only a pull
request with no usable record asks it, and then falls back to the default branch.
A record fetched more than a minute ago reads as `stale`, which every one here is.
Fetching, refusals, and account and rate-limit states are in
`tests/test_cli_github_pull_golden.py`.

## Test: a pull-request URL pins the head and shows the cached record

The pin is the head commit, which only `refs/pull/7/head` reaches.
`comparison_route` is Files changed: the merge base of the mirror’s `topic` and the
head, to the head.

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/7 --api /api/plugin/github/pull
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 7,
  "pin": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
  "fetched_at": "2026-09-17T12:00:00Z",
  "fresh_for_s": 60.0,
  "comparison_route": "/api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=85fcb2fa9e77eb5db485ffef445cbbc645d6db4a&base_policy=merge_base",
  "record": {
    "schema_version": 1,
    "source": "https://github.com/octo/demo",
    "number": 7,
    "fetched_at": "2026-09-17T12:00:00Z",
    "reader": "gh:octo-reader",
    "etags": {
      "repos/octo/demo/pulls/7": "W/\"865983808811b03c59b073a9a553cdda8094f3bc07611317ea924210341c8089\"",
      "repos/octo/demo/issues/7/comments?per_page=100&page=1": "W/\"129ba5d41c7ad9dc46b0ecc3d92124b83747ed95e5ff5422603eb05b99399608\"",
      "repos/octo/demo/pulls/7/reviews?per_page=100&page=1": "W/\"553dbffc68c21141af1083cb13e8be39e4138e90d4011da721d679e7853c5e9d\"",
      "repos/octo/demo/pulls/7/comments?per_page=100&page=1": "W/\"b4ca741eae91bcff3445421bd4f16ee7b2ae05d25fa979346f04a378ee3bd6cc\"",
      "repos/octo/demo/commits/85fcb2fa9e77eb5db485ffef445cbbc645d6db4a/check-runs?per_page=100&page=1": "W/\"8b11f63f1595a605256b810ecbc6ad42f31ec79413e5748815f151c4ed6821e8\"",
      "repos/octo/demo/commits/85fcb2fa9e77eb5db485ffef445cbbc645d6db4a/status?per_page=100&page=1": "W/\"7362c7bd7021c47983e06eb57cbc2d2b436158c6a1ec5f3fdeda0be1cc45832f\""
    },
    "pull": {
      "number": 7,
      "title": "Count to two in the app",
      "body": "The app counts to one.\r\n\r\nThis teaches it **two**.",
      "body_truncated": false,
      "state": "open",
      "draft": false,
      "merged": false,
      "merge_commit_sha": null,
      "mergeable": "mergeable",
      "labels": [
        "enhancement"
      ],
      "author": "forker",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "merged_at": null,
      "closed_at": null,
      "base": {
        "ref": "topic",
        "sha": "07b55f07793d9ed4e9f3e130c4414d979137bc53",
        "repository": "octo/demo"
      },
      "head": {
        "ref": "count-to-two",
        "sha": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "repository": "forker/demo"
      },
      "html_url": "https://github.com/octo/demo/pull/7"
    },
    "issue_comments": [
      {
        "id": 3341937855,
        "author": "maintainer",
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
        "body": "",
        "body_truncated": false,
        "submitted_at": "2026-09-16T12:32:50Z",
        "commit_id": "f7c5a9918657080d6aeb455902615b6e17df760a"
      },
      {
        "id": 3279967139,
        "state": "APPROVED",
        "author": "maintainer",
        "body": "Looks right.",
        "body_truncated": false,
        "submitted_at": "2026-09-16T17:36:02Z",
        "commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
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
        "commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "original_commit_id": "f7c5a9918657080d6aeb455902615b6e17df760a",
        "diff_hunk": "@@ -1 +1 @@\n-one\n+one",
        "diff_hunk_truncated": false,
        "author": "maintainer",
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
        "commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "original_commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "diff_hunk": "@@ -1 +1,2 @@\n one\n+two",
        "diff_hunk_truncated": false,
        "author": "forker",
        "body": "It no longer does; the second line is new.",
        "body_truncated": false,
        "created_at": "2026-09-16T17:30:11Z",
        "updated_at": "2026-09-16T17:30:11Z"
      }
    ],
    "check_runs": [
      {
        "id": 51401654787,
        "name": "tests (3.13)",
        "status": "completed",
        "conclusion": "success",
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
        "app": "GitHub Actions"
      },
      {
        "id": 51401654788,
        "name": "docs",
        "status": "in_progress",
        "conclusion": null,
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
        "app": "GitHub Actions"
      }
    ],
    "status": {
      "state": "success",
      "statuses": [
        {
          "context": "docs/readthedocs.org:demo",
          "state": "success",
          "description": "Read the Docs build succeeded!",
          "target_url": "https://demo--7.org.readthedocs.build/en/7/"
        }
      ]
    },
    "comparison": {
      "base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
      "base_commit": "c691256511d05858850bc7684ae062fea0d41132",
      "base_from": "base_branch"
    },
    "truncated": {
      "issue_comments": false,
      "reviews": false,
      "review_comments": false,
      "check_runs": false,
      "statuses": false,
      "text": false
    },
    "unavailable": {}
  }
}
? 0
```

## Test: Files changed is the merge-base comparison

`base_policy` passes through the diff plugin’s comparison route, so the document says
how its base was chosen.
`README.md`, which changed on `topic` after the fork point, is not in it.

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=85fcb2fa9e77eb5db485ffef445cbbc645d6db4a&base_policy=merge_base'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=85fcb2fa9e77eb5db485ffef445cbbc645d6db4a&base_policy=merge_base
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:9479019c56eedd23",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "merge_base",
    "left": {
      "kind": "commit",
      "id": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "symbolic": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b"
    },
    "right": {
      "kind": "commit",
      "id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
      "symbolic": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
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
        "kind": "added",
        "new": {
          "path": "docs/new.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "e65f941eafc191b1242e9ef5170ab3426ef3c42b"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 1,
        "deletions": 0
      },
      {
        "id": "f2",
        "kind": "modified",
        "old": {
          "path": "src/app.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "5626abf0f72e58d7a153368ba57db4c673c0e171"
          }
        },
        "new": {
          "path": "src/app.txt",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "814f4a422927b82f5f8a43f8fab6d3839e3983f2"
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
          "old_start": 0,
          "old_count": 0,
          "new_start": 1,
          "new_count": 1,
          "lines": [
            {
              "op": "add",
              "text": "# New",
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
          "old_start": 1,
          "old_count": 1,
          "new_start": 1,
          "new_count": 2,
          "lines": [
            {
              "op": "context",
              "text": "one",
              "no_newline": false
            },
            {
              "op": "add",
              "text": "two",
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

## Test: a merged pull request compares from its base.sha

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/8 --api '/api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=8ae27617c9c475851b67ee69433d008836d112ba&base_policy=merge_base'
selection: pull_request
pin: 8ae27617c9c475851b67ee69433d008836d112ba (pull request 8 head)
pull_request: 8 (merged; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=8ae27617c9c475851b67ee69433d008836d112ba&base_policy=merge_base
status: 200
{
  "schema": "file-diff-v1",
  "schema_version": 1,
  "resolved": {
    "comparison_id": "git:56a857bc09d81107",
    "source": {
      "name": "git"
    },
    "kind": "content",
    "base_policy": "merge_base",
    "left": {
      "kind": "commit",
      "id": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "symbolic": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b"
    },
    "right": {
      "kind": "commit",
      "id": "8ae27617c9c475851b67ee69433d008836d112ba",
      "symbolic": "8ae27617c9c475851b67ee69433d008836d112ba"
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
          "path": "docs/guide.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "8c0d02fadc02df29eefff5ad660a022b4a8e5efd"
          }
        },
        "new": {
          "path": "docs/guide.md",
          "entry_type": "file",
          "mode": "100644",
          "content": {
            "kind": "git_object",
            "oid": "a152cb3700eaceb6b10ca7a919f23747685c9b43"
          }
        },
        "binary": false,
        "availability": "ready",
        "additions": 2,
        "deletions": 0
      }
    ],
    "totals": {
      "files": 1,
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
              "text": "# Guide",
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
    }
  }
}
? 0
```

## Test: a closed pull request whose fork is gone

`head.repository` is `null`, and the comparison starts from a `base.sha` that the
refresh fetched by ID.

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/9 --api /api/plugin/github/pull
selection: pull_request
pin: 0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd (pull request 9 head)
pull_request: 9 (closed; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 9,
  "pin": "0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd",
  "fetched_at": "2026-09-17T12:00:00Z",
  "fresh_for_s": 60.0,
  "comparison_route": "/api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd&base_policy=merge_base",
  "record": {
    "schema_version": 1,
    "source": "https://github.com/octo/demo",
    "number": 9,
    "fetched_at": "2026-09-17T12:00:00Z",
    "reader": "gh:octo-reader",
    "etags": {
      "repos/octo/demo/pulls/9": "W/\"83ce79bd9830fa4ab7967fc4d84b8e996e7fa0bcd9ff1d369c6f136815a2eff8\"",
      "repos/octo/demo/issues/9/comments?per_page=100&page=1": "W/\"8e3fb7499c48198e2722d4bf87b6c307d9dd9f38dc4d767cb6d084933715125a\"",
      "repos/octo/demo/pulls/9/reviews?per_page=100&page=1": "W/\"7f0bc5191955ee595d16f9154007d0dc93786fa2ababd3d3aeb87531c7dbc19a\"",
      "repos/octo/demo/pulls/9/comments?per_page=100&page=1": "W/\"d3923abb607ffe393dc70a9b0bb679b48cf6c97b158f065d3879327d52e2bbe4\"",
      "repos/octo/demo/commits/0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd/check-runs?per_page=100&page=1": "W/\"9d896926c34fed29e7ea8b7d6720a3bf34b3092b36ce69595693cd87c39c8277\"",
      "repos/octo/demo/commits/0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd/status?per_page=100&page=1": "W/\"955c010f49492dffc671eb66fd59042f2a5f78427d63ccb457d71cf2cae4f2bd\""
    },
    "pull": {
      "number": 9,
      "title": "spam",
      "body": "",
      "body_truncated": false,
      "state": "closed",
      "draft": false,
      "merged": false,
      "merge_commit_sha": null,
      "mergeable": "unknown",
      "labels": [
        "invalid"
      ],
      "author": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "merged_at": null,
      "closed_at": "2026-09-16T19:00:00Z",
      "base": {
        "ref": "topic",
        "sha": "c1063e6e9a97345a8c7e1dc275c7fd858c91d7b3",
        "repository": "octo/demo"
      },
      "head": {
        "ref": "spam",
        "sha": "0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd",
        "repository": null
      },
      "html_url": "https://github.com/octo/demo/pull/9"
    },
    "issue_comments": [],
    "reviews": [],
    "review_comments": [],
    "check_runs": [
      {
        "id": 51401654787,
        "name": "tests (3.13)",
        "status": "completed",
        "conclusion": "success",
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
        "app": "GitHub Actions"
      },
      {
        "id": 51401654788,
        "name": "docs",
        "status": "in_progress",
        "conclusion": null,
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
        "app": "GitHub Actions"
      }
    ],
    "status": {
      "state": "success",
      "statuses": [
        {
          "context": "docs/readthedocs.org:demo",
          "state": "success",
          "description": "Read the Docs build succeeded!",
          "target_url": "https://demo--7.org.readthedocs.build/en/7/"
        }
      ]
    },
    "comparison": {
      "base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "head": "0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd",
      "base_commit": "c1063e6e9a97345a8c7e1dc275c7fd858c91d7b3",
      "base_from": "base_sha"
    },
    "truncated": {
      "issue_comments": false,
      "reviews": false,
      "review_comments": false,
      "check_runs": false,
      "statuses": false,
      "text": false
    },
    "unavailable": {}
  }
}
? 0
```

## Test: a draft pull request opens at its head

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/10/files --show docs/draft.md
selection: pull_request
pin: 7a7d6596e515735d244dc1d942463c95851e139c (pull request 10 head)
pull_request: 10 (draft; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
show: docs/draft.md
route: /view/g1-ZG9jcw/g1-ZHJhZnQubWQ
kind: markdown
views: rendered (default), source
model: text envelope; size=8 content_bytes=8 content_truncated=False
? 0
```

## Test: a commit URL inside a pull request can name a fork’s commit

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/7/commits/f7c5a99 --api /api/plugin/github/pull
selection: commit
pin: f7c5a9918657080d6aeb455902615b6e17df760a (commit)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 7,
  "pin": "f7c5a9918657080d6aeb455902615b6e17df760a",
  "fetched_at": "2026-09-17T12:00:00Z",
  "fresh_for_s": 60.0,
  "comparison_route": "/api/plugin/diff/comparison?left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=85fcb2fa9e77eb5db485ffef445cbbc645d6db4a&base_policy=merge_base",
  "record": {
    "schema_version": 1,
    "source": "https://github.com/octo/demo",
    "number": 7,
    "fetched_at": "2026-09-17T12:00:00Z",
    "reader": "gh:octo-reader",
    "etags": {
      "repos/octo/demo/pulls/7": "W/\"865983808811b03c59b073a9a553cdda8094f3bc07611317ea924210341c8089\"",
      "repos/octo/demo/issues/7/comments?per_page=100&page=1": "W/\"129ba5d41c7ad9dc46b0ecc3d92124b83747ed95e5ff5422603eb05b99399608\"",
      "repos/octo/demo/pulls/7/reviews?per_page=100&page=1": "W/\"553dbffc68c21141af1083cb13e8be39e4138e90d4011da721d679e7853c5e9d\"",
      "repos/octo/demo/pulls/7/comments?per_page=100&page=1": "W/\"b4ca741eae91bcff3445421bd4f16ee7b2ae05d25fa979346f04a378ee3bd6cc\"",
      "repos/octo/demo/commits/85fcb2fa9e77eb5db485ffef445cbbc645d6db4a/check-runs?per_page=100&page=1": "W/\"8b11f63f1595a605256b810ecbc6ad42f31ec79413e5748815f151c4ed6821e8\"",
      "repos/octo/demo/commits/85fcb2fa9e77eb5db485ffef445cbbc645d6db4a/status?per_page=100&page=1": "W/\"7362c7bd7021c47983e06eb57cbc2d2b436158c6a1ec5f3fdeda0be1cc45832f\""
    },
    "pull": {
      "number": 7,
      "title": "Count to two in the app",
      "body": "The app counts to one.\r\n\r\nThis teaches it **two**.",
      "body_truncated": false,
      "state": "open",
      "draft": false,
      "merged": false,
      "merge_commit_sha": null,
      "mergeable": "mergeable",
      "labels": [
        "enhancement"
      ],
      "author": "forker",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "merged_at": null,
      "closed_at": null,
      "base": {
        "ref": "topic",
        "sha": "07b55f07793d9ed4e9f3e130c4414d979137bc53",
        "repository": "octo/demo"
      },
      "head": {
        "ref": "count-to-two",
        "sha": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "repository": "forker/demo"
      },
      "html_url": "https://github.com/octo/demo/pull/7"
    },
    "issue_comments": [
      {
        "id": 3341937855,
        "author": "maintainer",
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
        "body": "",
        "body_truncated": false,
        "submitted_at": "2026-09-16T12:32:50Z",
        "commit_id": "f7c5a9918657080d6aeb455902615b6e17df760a"
      },
      {
        "id": 3279967139,
        "state": "APPROVED",
        "author": "maintainer",
        "body": "Looks right.",
        "body_truncated": false,
        "submitted_at": "2026-09-16T17:36:02Z",
        "commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
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
        "commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "original_commit_id": "f7c5a9918657080d6aeb455902615b6e17df760a",
        "diff_hunk": "@@ -1 +1 @@\n-one\n+one",
        "diff_hunk_truncated": false,
        "author": "maintainer",
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
        "commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "original_commit_id": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
        "diff_hunk": "@@ -1 +1,2 @@\n one\n+two",
        "diff_hunk_truncated": false,
        "author": "forker",
        "body": "It no longer does; the second line is new.",
        "body_truncated": false,
        "created_at": "2026-09-16T17:30:11Z",
        "updated_at": "2026-09-16T17:30:11Z"
      }
    ],
    "check_runs": [
      {
        "id": 51401654787,
        "name": "tests (3.13)",
        "status": "completed",
        "conclusion": "success",
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
        "app": "GitHub Actions"
      },
      {
        "id": 51401654788,
        "name": "docs",
        "status": "in_progress",
        "conclusion": null,
        "details_url": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
        "app": "GitHub Actions"
      }
    ],
    "status": {
      "state": "success",
      "statuses": [
        {
          "context": "docs/readthedocs.org:demo",
          "state": "success",
          "description": "Read the Docs build succeeded!",
          "target_url": "https://demo--7.org.readthedocs.build/en/7/"
        }
      ]
    },
    "comparison": {
      "base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
      "base_commit": "c691256511d05858850bc7684ae062fea0d41132",
      "base_from": "base_branch"
    },
    "truncated": {
      "issue_comments": false,
      "reviews": false,
      "review_comments": false,
      "check_runs": false,
      "statuses": false,
      "text": false
    },
    "unavailable": {}
  }
}
? 0
```

## Test: a repository URL selects no pull request

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pull
api: /api/plugin/github/pull
status: 200
{
  "state": "absent",
  "reason": "no_pull_request",
  "source": null,
  "number": null,
  "pin": null,
  "fetched_at": null,
  "fresh_for_s": 60.0,
  "comparison_route": null,
  "record": null
}
? 0
```

## Test: a pull request with no usable record answers why

Nothing is cached for 14; 12 holds a record from another schema; 13 holds something that
is not JSON. Each asks the failing `gh` once, falls back to the default branch, and the
route says why it has nothing to show.

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/14 --api /api/plugin/github/pull
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 14 (not opened: pull request 14 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
api: /api/plugin/github/pull
status: 200
{
  "state": "absent",
  "reason": "not_cached",
  "source": "https://github.com/octo/demo",
  "number": 14,
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "fetched_at": null,
  "fresh_for_s": 60.0,
  "comparison_route": null,
  "record": null
}
? 0
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/12 --api /api/plugin/github/pull
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 12 (not opened: pull request 12 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
api: /api/plugin/github/pull
status: 200
{
  "state": "absent",
  "reason": "schema_mismatch",
  "source": "https://github.com/octo/demo",
  "number": 12,
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "fetched_at": null,
  "fresh_for_s": 60.0,
  "comparison_route": null,
  "record": null
}
? 0
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/13 --api /api/plugin/github/pull
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 13 (not opened: pull request 13 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
api: /api/plugin/github/pull
status: 200
{
  "state": "absent",
  "reason": "unreadable",
  "source": "https://github.com/octo/demo",
  "number": 13,
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "fetched_at": null,
  "fresh_for_s": 60.0,
  "comparison_route": null,
  "record": null
}
? 0
```

## Test: the cache still reads the source as published

The pull-request records live beside the source’s own records, where nothing reads them
as damage.

```console
$ METABROWSER_HOME=$PWD/home metab root --api /api/cache/source/github-com--octo--demo--46386669dc01 | grep -E '"(publication|problems)"'
    "publication": "published",
    "problems": [],
      "publication": "published",
      "problems": []
? 0
```
