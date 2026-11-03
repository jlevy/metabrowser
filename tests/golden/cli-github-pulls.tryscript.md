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
patterns:
  TIMESTAMP: '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'
  APP_HOME: '[^\s"]+/home'
before: >-
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" .
  > fixture.log 2>&1 &&
  printf '{}\n' > refresh.json &&
  printf '{"state": "merged"}\n' > bad-state.json &&
  mkdir folder
---
# Golden tests: lists of pull requests from the cache

`tests/github_pull_fixture.py` builds `home` before these commands run: a mirror of
`https://github.com/octo/demo` and, with a fake `gh` and a clock fixed at
2026-09-17T12:00:00Z, these lists of its pull requests:

| List | Held |
| --- | --- |
| `all`, the default | One full page, 106 down to 7, and GitHub has more |
| `open` | 10 and 7, complete, as another account read it |
| `closed` | Nothing |

Every command below answers from that cache, and none reaches the network or needs a Git
the acquisition floor admits.
`gh` is `tests/fixtures/github-pull/no-gh/gh`, which fails every command, so a read that
asked it would show.
A list fetched more than a minute ago reads as `stale`, which every one here is.
A refresh that completes and a list that is `current` are in
`tests/golden/cli-github-pulls-refresh.txt`, and each typed failure in
`tests/golden/cli-github-pulls-failures.txt`.

## Test: the default list is `all`, a window of its rows at a time

No `state` means `all`. `fetched` is how many rows are held, `complete` is false because
the last page read had a next page, and `next_after` is where the next window starts.
A row keeps what a list shows: GitHub’s description, repository objects, and URLs are
not in it, and `merged` is read from `merged_at`.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?limit=2'
api: /api/plugin/github/pulls?limit=2
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "all",
  "fetched_at": "2026-09-17T12:00:00Z",
  "reader": "gh:octo-reader",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 100,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 2,
  "next_after": 105,
  "rows": [
    {
      "number": 106,
      "title": "Work item 106",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "created_at": "2026-09-17T09:46:00Z",
      "updated_at": "2026-09-17T09:46:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-106",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": false
    },
    {
      "number": 105,
      "title": "Work item 105",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "created_at": "2026-09-17T09:45:00Z",
      "updated_at": "2026-09-17T09:45:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-105",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": false
    }
  ]
}
? 0
```

## Test: the next window starts after a row’s number

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?state=all&limit=2&after=105'
api: /api/plugin/github/pulls?state=all&limit=2&after=105
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "all",
  "fetched_at": "2026-09-17T12:00:00Z",
  "reader": "gh:octo-reader",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 100,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 2,
  "next_after": 103,
  "rows": [
    {
      "number": 104,
      "title": "Work item 104",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "created_at": "2026-09-17T09:44:00Z",
      "updated_at": "2026-09-17T09:44:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-104",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": false
    },
    {
      "number": 103,
      "title": "Work item 103",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "created_at": "2026-09-17T09:43:00Z",
      "updated_at": "2026-09-17T09:43:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-103",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": false
    }
  ]
}
? 0
```

## Test: the last window ends the cached rows of an incomplete list

`next_after` is null here because no cached row is left, and `complete` is still false,
because GitHub has more.
The four rows are an open draft, a closed pull request whose fork was deleted, a merged
one, and an open one from a fork.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?limit=4&after=11'
api: /api/plugin/github/pulls?limit=4&after=11
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "all",
  "fetched_at": "2026-09-17T12:00:00Z",
  "reader": "gh:octo-reader",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 100,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 4,
  "next_after": null,
  "rows": [
    {
      "number": 10,
      "title": "WIP: draft the next page",
      "state": "open",
      "draft": true,
      "merged_at": null,
      "author": "maintainer",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "wip",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": false
    },
    {
      "number": 9,
      "title": "spam",
      "state": "closed",
      "draft": false,
      "merged_at": null,
      "author": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": "2026-09-16T19:00:00Z",
      "base_ref": "topic",
      "head_ref": "spam",
      "head_repository": null,
      "labels": [
        "invalid"
      ],
      "merged": false
    },
    {
      "number": 8,
      "title": "Say more in the guide",
      "state": "closed",
      "draft": false,
      "merged_at": "2026-09-16T18:00:00Z",
      "author": "maintainer",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": "2026-09-16T18:00:00Z",
      "base_ref": "topic",
      "head_ref": "guide-more",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": true
    },
    {
      "number": 7,
      "title": "Count to two in the app",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "forker",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "count-to-two",
      "head_repository": "forker/demo",
      "labels": [
        "enhancement"
      ],
      "merged": false
    }
  ]
}
? 0
```

## Test: `limit=0` answers the envelope alone

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?limit=0'
api: /api/plugin/github/pulls?limit=0
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "all",
  "fetched_at": "2026-09-17T12:00:00Z",
  "reader": "gh:octo-reader",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 100,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 0,
  "next_after": null,
  "rows": []
}
? 0
```

## Test: a list another account fetched is shown as it is, labelled with its reader

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?state=open'
api: /api/plugin/github/pulls?state=open
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "open",
  "fetched_at": "2026-09-17T12:00:00Z",
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 2,
  "complete": true,
  "truncated": false,
  "at_cap": false,
  "limit": 100,
  "next_after": null,
  "rows": [
    {
      "number": 10,
      "title": "WIP: draft the next page",
      "state": "open",
      "draft": true,
      "merged_at": null,
      "author": "maintainer",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "wip",
      "head_repository": "octo/demo",
      "labels": [],
      "merged": false
    },
    {
      "number": 7,
      "title": "Count to two in the app",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "forker",
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "count-to-two",
      "head_repository": "forker/demo",
      "labels": [
        "enhancement"
      ],
      "merged": false
    }
  ]
}
? 0
```

## Test: a list nothing has fetched is absent, and a read does not fetch it

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?state=closed'
api: /api/plugin/github/pulls?state=closed
status: 200
{
  "state": "absent",
  "reason": "not_cached",
  "source": "https://github.com/octo/demo",
  "list": "closed",
  "fetched_at": null,
  "reader": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": null,
  "fetched": 0,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 100,
  "next_after": null,
  "rows": []
}
? 0
```

## Test: a request the route cannot answer is refused

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?state=merged'
api: /api/plugin/github/pulls?state=merged
status: 400
{
  "error": "\"state\" is all, open, or closed",
  "code": "invalid_request"
}
Error: /api/plugin/github/pulls?state=merged returned HTTP 400
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?limit=1001'
api: /api/plugin/github/pulls?limit=1001
status: 400
{
  "error": "\"limit\" is a whole number from 0 to 1000",
  "code": "invalid_request"
}
Error: /api/plugin/github/pulls?limit=1001 returned HTTP 400
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pulls-refresh --data bad-state.json
api: /api/plugin/github/pulls-refresh
status: 400
{
  "error": "\"state\" is all, open, or closed",
  "code": "invalid_request"
}
Error: /api/plugin/github/pulls-refresh returned HTTP 400
? 1
```

## Test: a folder has no repository to list

Nothing is read and nothing is started.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab folder --api '/api/plugin/github/pulls?limit=0'
api: /api/plugin/github/pulls?limit=0
status: 200
{
  "state": "absent",
  "reason": "not_github",
  "source": null,
  "list": "all",
  "fetched_at": null,
  "reader": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": null,
  "fetched": 0,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 0,
  "next_after": null,
  "rows": []
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab folder --api /api/plugin/github/pulls-refresh --data refresh.json
api: /api/plugin/github/pulls-refresh
status: 409
{
  "error": "this server serves no GitHub repository",
  "code": "not_github"
}
Error: /api/plugin/github/pulls-refresh returned HTTP 409
? 1
```

## Test: the list’s address reports its kind and its state

`/pulls` is the list with no pull request selected, and `?state=` names its filter.
`--show` reports what the Pulls tab renders it from, without its rows: its state and its
honest count. It reads the cache alone, as the tab’s first read does.
A filter the list does not have is the route’s to refuse, and a folder’s server answers
the same address with nothing to list.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show /pulls
show: /pulls
route: /pulls
kind: pull-request-list
views: pull-request-list (default)
model: pull-request list envelope; state=stale list=all fetched=100 complete=False truncated=False at_cap=False refreshing=False reader=gh:octo-reader fetched_at=2026-09-17T12:00:00Z
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show '/pulls?state=open'
show: /pulls?state=open
route: /pulls?state=open
kind: pull-request-list
views: pull-request-list (default)
model: pull-request list envelope; state=stale list=open fetched=2 complete=True truncated=False at_cap=False refreshing=False reader=gh:someone-else fetched_at=2026-09-17T12:00:00Z
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show '/pulls?state=merged'
Error: /pulls?state=merged is not a selection the browser can open (HTTP 400)
? 1
```

```console
$ metab folder --show /pulls
show: /pulls
route: /pulls
kind: pull-request-list
views: pull-request-list (default)
model: pull-request list envelope; state=absent list=all reason=not_github fetched=0 complete=False truncated=False at_cap=False refreshing=False
? 0
```

## Test: a refresh returns at once, and the command says how it ended

`pulls-refresh` starts the list’s refresh in the refresh coordinator and answers `202`
without waiting for it, with the envelope as of that moment, without rows.
`status_route` names the route that reports how it ended: the one-shot command waits for
the refresh, prints that route `after` it, and exits 1 when it failed.
Here `gh` fails, so the command exits 1, and the cached list stands.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pulls-refresh --data refresh.json
api: /api/plugin/github/pulls-refresh
status: 202
{
  "refresh": "started",
  "pulls": {
    "state": "stale",
    "reason": null,
    "source": "https://github.com/octo/demo",
    "list": "all",
    "fetched_at": "2026-09-17T12:00:00Z",
    "reader": "gh:octo-reader",
    "fresh_for_s": 60.0,
    "refreshing": true,
    "last_refresh": {
      "outcome": "succeeded",
      "message": null,
      "reset_at": null,
      "at": "2026-09-17T12:00:00Z"
    },
    "fetched": 100,
    "complete": false,
    "truncated": false,
    "at_cap": false,
    "limit": 0,
    "next_after": null,
    "rows": []
  },
  "status_route": "/api/plugin/github/pulls?state=all&limit=0"
}
after: /api/plugin/github/pulls?state=all&limit=0
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "all",
  "fetched_at": "2026-09-17T12:00:00Z",
  "reader": "gh:octo-reader",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "gh_failed",
    "message": "gh exited 1 without an HTTP response",
    "reset_at": null,
    "at": "[TIMESTAMP]"
  },
  "fetched": 100,
  "complete": false,
  "truncated": false,
  "at_cap": false,
  "limit": 0,
  "next_after": null,
  "rows": []
}
Error: the refresh ended with gh_failed
? 1
```

## Test: within the window, an automatic request starts nothing

The attempt above is under a minute old, so this one is `not_due`, answered `200`, and
`gh` is not asked again.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pulls-refresh --data refresh.json
api: /api/plugin/github/pulls-refresh
status: 200
{
  "refresh": "not_due",
  "pulls": {
    "state": "stale",
    "reason": null,
    "source": "https://github.com/octo/demo",
    "list": "all",
    "fetched_at": "2026-09-17T12:00:00Z",
    "reader": "gh:octo-reader",
    "fresh_for_s": 60.0,
    "refreshing": false,
    "last_refresh": {
      "outcome": "gh_failed",
      "message": "gh exited 1 without an HTTP response",
      "reset_at": null,
      "at": "[TIMESTAMP]"
    },
    "fetched": 100,
    "complete": false,
    "truncated": false,
    "at_cap": false,
    "limit": 0,
    "next_after": null,
    "rows": []
  },
  "status_route": "/api/plugin/github/pulls?state=all&limit=0"
}
? 0
```
