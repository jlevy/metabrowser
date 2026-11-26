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
  METABROWSER_CONFIG_DIR="$PWD/config"
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

The shared catalog contains 102 PRs (100 Open and two Closed, including one merged),
last read by another account.
Its opaque epoch is fixed by the fixture, as its clock is.

Every command below answers from that cache, and none reaches the network or needs a Git
the acquisition floor admits.
`gh` is `tests/fixtures/github-pull/no-gh/gh`, which fails every command, so a read that
asked it would show.
A list fetched more than a minute ago reads as `stale`, which every one here is.
A refresh that completes and a list that is `current` are in
`tests/golden/cli-github-pulls-refresh.txt`, and each typed failure in
`tests/golden/cli-github-pulls-failures.txt`.

## Test: the default list is Open, a window of cached rows at a time

No `state` means `open`. `total` is the exact selected-filter count, `repository_total`
is the exact all-PR count, and `catalog_fetched` says how much metadata is cached.
The complete catalog remains separate from each bounded response window; `next_after`
names the next cached window.
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
  "list": "open",
  "fetched_at": "2026-09-17T12:00:00Z",
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "total": 100,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:0",
  "fetched": 100,
  "complete": true,
  "truncated": false,
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
      "author_avatar_url": null,
      "created_at": "2026-09-17T09:46:00Z",
      "updated_at": "2026-09-17T09:46:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-106",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    },
    {
      "number": 105,
      "title": "Work item 105",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "author_avatar_url": null,
      "created_at": "2026-09-17T09:45:00Z",
      "updated_at": "2026-09-17T09:45:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-105",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
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
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "total": 102,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:2",
  "fetched": 102,
  "complete": true,
  "truncated": false,
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
      "author_avatar_url": null,
      "created_at": "2026-09-17T09:44:00Z",
      "updated_at": "2026-09-17T09:44:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-104",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    },
    {
      "number": 103,
      "title": "Work item 103",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "author_avatar_url": null,
      "created_at": "2026-09-17T09:43:00Z",
      "updated_at": "2026-09-17T09:43:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-103",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    }
  ]
}
? 0
```

## Test: the last window ends the cached Open rows

`next_after` is null because no cached Open row remains; `complete` is true because the
catalog holds the complete list.
The window includes a draft and a PR from a fork; Closed rows are projected separately
below.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?limit=4&after=11'
api: /api/plugin/github/pulls?limit=4&after=11
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "open",
  "fetched_at": "2026-09-17T12:00:00Z",
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "total": 100,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:0",
  "fetched": 100,
  "complete": true,
  "truncated": false,
  "limit": 4,
  "next_after": null,
  "rows": [
    {
      "number": 6,
      "title": "Work item 6",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "author_avatar_url": null,
      "created_at": "2026-09-17T08:06:00Z",
      "updated_at": "2026-09-17T08:06:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-6",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    },
    {
      "number": 5,
      "title": "Work item 5",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "author_avatar_url": null,
      "created_at": "2026-09-17T08:05:00Z",
      "updated_at": "2026-09-17T08:05:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-5",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    },
    {
      "number": 10,
      "title": "WIP: draft the next page",
      "state": "open",
      "draft": true,
      "merged_at": null,
      "author": "maintainer",
      "author_avatar_url": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "wip",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "7a7d6596e515735d244dc1d942463c95851e139c",
      "merged": false
    },
    {
      "number": 7,
      "title": "Count to two in the app",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "forker",
      "author_avatar_url": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "count-to-two",
      "head_repository": "forker/demo",
      "labels": [
        "enhancement"
      ],
      "head_oid": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
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
  "list": "open",
  "fetched_at": "2026-09-17T12:00:00Z",
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "total": 100,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:0",
  "fetched": 100,
  "complete": true,
  "truncated": false,
  "limit": 0,
  "next_after": null,
  "rows": []
}
? 0
```

## Test: a list another account fetched is shown as it is, labelled with its reader

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?state=open&after=11&limit=2'
api: /api/plugin/github/pulls?state=open&after=11&limit=2
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "open",
  "fetched_at": "2026-09-17T12:00:00Z",
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "total": 100,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:0",
  "fetched": 100,
  "complete": true,
  "truncated": false,
  "limit": 2,
  "next_after": 5,
  "rows": [
    {
      "number": 6,
      "title": "Work item 6",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "author_avatar_url": null,
      "created_at": "2026-09-17T08:06:00Z",
      "updated_at": "2026-09-17T08:06:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-6",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    },
    {
      "number": 5,
      "title": "Work item 5",
      "state": "open",
      "draft": false,
      "merged_at": null,
      "author": "contributor",
      "author_avatar_url": null,
      "created_at": "2026-09-17T08:05:00Z",
      "updated_at": "2026-09-17T08:05:00Z",
      "closed_at": null,
      "base_ref": "topic",
      "head_ref": "work-5",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "0000000000000000000000000000000000000000",
      "merged": false
    }
  ]
}
? 0
```

## Test: Closed rows come from the shared catalog without fetching

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pulls?state=closed'
api: /api/plugin/github/pulls?state=closed
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "closed",
  "fetched_at": "2026-09-17T12:00:00Z",
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "total": 2,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:1",
  "fetched": 2,
  "complete": true,
  "truncated": false,
  "limit": 100,
  "next_after": null,
  "rows": [
    {
      "number": 9,
      "title": "spam",
      "state": "closed",
      "draft": false,
      "merged_at": null,
      "author": null,
      "author_avatar_url": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": "2026-09-16T19:00:00Z",
      "base_ref": "topic",
      "head_ref": "spam",
      "head_repository": null,
      "labels": [
        "invalid"
      ],
      "head_oid": "0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd",
      "merged": false
    },
    {
      "number": 8,
      "title": "Say more in the guide",
      "state": "closed",
      "draft": false,
      "merged_at": "2026-09-16T18:00:00Z",
      "author": "maintainer",
      "author_avatar_url": null,
      "created_at": "2026-09-16T10:57:23Z",
      "updated_at": "2026-09-16T17:39:01Z",
      "closed_at": "2026-09-16T18:00:00Z",
      "base_ref": "topic",
      "head_ref": "guide-more",
      "head_repository": "octo/demo",
      "labels": [],
      "head_oid": "8ae27617c9c475851b67ee69433d008836d112ba",
      "merged": true
    }
  ]
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
  "error": "\"limit\" is outside its allowed range",
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
  "list": "open",
  "fetched_at": null,
  "checked_at": null,
  "reader": null,
  "fresh_for_s": 60.0,
  "probe_every_s": null,
  "refreshing": false,
  "last_refresh": null,
  "total": null,
  "repository_total": null,
  "filter_totals": null,
  "count_at": null,
  "catalog_fetched": 0,
  "generation": null,
  "fetched": 0,
  "complete": false,
  "truncated": false,
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

## Test: a branch that is a pull request’s head shows it in the ref list

The ref chooser lists the mirror’s branches (`/api/source/refs`), and a branch that is
the head of a pull request in this catalog lists it on its row, with the state the Pulls
tab shows.
Only a pull request from the repository’s own branch is a branch’s: #7 is from
a fork and #9’s fork is gone, so neither names a branch, and `wip`, #10’s head, is a
draft. `topic`, the default, is the head of none, so its row has no `pulls`. The listing
reads the cache alone: `gh` here fails every command, and `pull_requests` says the
catalog is cached, so a page that sees it does not ask again.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/source/refs?kind=branch'
api: /api/source/refs?kind=branch
status: 200
{
  "kind": "branch",
  "query": "",
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "ref": "refs/remotes/origin/topic",
  "kinds": [
    "branch",
    "tag"
  ],
  "working_tree": null,
  "origin": null,
  "pull_requests": {
    "state": "ready",
    "complete": true,
    "refreshing": false
  },
  "refs": [
    {
      "name": "topic",
      "ref": "refs/remotes/origin/topic",
      "commit": "c691256511d05858850bc7684ae062fea0d41132",
      "committed_at": 1788021600.0,
      "default": true,
      "checked_out": false,
      "current": true
    },
    {
      "name": "wip",
      "ref": "refs/remotes/origin/wip",
      "commit": "7a7d6596e515735d244dc1d942463c95851e139c",
      "committed_at": 1788032400.0,
      "default": false,
      "checked_out": false,
      "current": false,
      "pulls": [
        {
          "number": 10,
          "title": "WIP: draft the next page",
          "state": "draft"
        }
      ],
      "pulls_total": 1
    }
  ]
}
? 0
```

The filter finds a branch by its pull request as well as by its name: `#` and the start
of a number, or every word of a title, in any case.
`#` alone is every pull request, so it lists the branches that have one.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/source/refs?kind=branch&q=%231'
api: /api/source/refs?kind=branch&q=%231
status: 200
{
  "kind": "branch",
  "query": "#1",
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "ref": "refs/remotes/origin/topic",
  "kinds": [
    "branch",
    "tag"
  ],
  "working_tree": null,
  "origin": null,
  "pull_requests": {
    "state": "ready",
    "complete": true,
    "refreshing": false
  },
  "refs": [
    {
      "name": "wip",
      "ref": "refs/remotes/origin/wip",
      "commit": "7a7d6596e515735d244dc1d942463c95851e139c",
      "committed_at": 1788032400.0,
      "default": false,
      "checked_out": false,
      "current": false,
      "pulls": [
        {
          "number": 10,
          "title": "WIP: draft the next page",
          "state": "draft"
        }
      ],
      "pulls_total": 1
    }
  ]
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/source/refs?kind=branch&q=NEXT+page'
api: /api/source/refs?kind=branch&q=NEXT+page
status: 200
{
  "kind": "branch",
  "query": "NEXT page",
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "ref": "refs/remotes/origin/topic",
  "kinds": [
    "branch",
    "tag"
  ],
  "working_tree": null,
  "origin": null,
  "pull_requests": {
    "state": "ready",
    "complete": true,
    "refreshing": false
  },
  "refs": [
    {
      "name": "wip",
      "ref": "refs/remotes/origin/wip",
      "commit": "7a7d6596e515735d244dc1d942463c95851e139c",
      "committed_at": 1788032400.0,
      "default": false,
      "checked_out": false,
      "current": false,
      "pulls": [
        {
          "number": 10,
          "title": "WIP: draft the next page",
          "state": "draft"
        }
      ],
      "pulls_total": 1
    }
  ]
}
? 0
```

A pull request whose branch the mirror does not hold lists nothing: #8’s title says
“guide”, and `guide-more`, its head, is merged and gone, so no row is its.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/source/refs?kind=branch&q=guide'
api: /api/source/refs?kind=branch&q=guide
status: 200
{
  "kind": "branch",
  "query": "guide",
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "ref": "refs/remotes/origin/topic",
  "kinds": [
    "branch",
    "tag"
  ],
  "working_tree": null,
  "origin": null,
  "pull_requests": {
    "state": "ready",
    "complete": true,
    "refreshing": false
  },
  "refs": []
}
? 0
```

A tag is no pull request’s head, so its list says it has no pull requests.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/source/refs?kind=tag'
api: /api/source/refs?kind=tag
status: 200
{
  "kind": "tag",
  "query": "",
  "pin": "c691256511d05858850bc7684ae062fea0d41132",
  "ref": "refs/remotes/origin/topic",
  "kinds": [
    "branch",
    "tag"
  ],
  "working_tree": null,
  "origin": null,
  "pull_requests": null,
  "refs": []
}
? 0
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
model: pull-request list envelope; state=stale list=open total=100 repository_total=102 catalog_fetched=102 fetched=100 complete=True truncated=False refreshing=False reader=gh:someone-else fetched_at=2026-09-17T12:00:00Z
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show '/pulls?state=open'
show: /pulls?state=open
route: /pulls?state=open
kind: pull-request-list
views: pull-request-list (default)
model: pull-request list envelope; state=stale list=open total=100 repository_total=102 catalog_fetched=102 fetched=100 complete=True truncated=False refreshing=False reader=gh:someone-else fetched_at=2026-09-17T12:00:00Z
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
model: pull-request list envelope; state=absent list=open reason=not_github total=None repository_total=None catalog_fetched=0 fetched=0 complete=False truncated=False refreshing=False
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
    "list": "open",
    "fetched_at": "2026-09-17T12:00:00Z",
    "checked_at": null,
    "reader": "gh:someone-else",
    "fresh_for_s": 60.0,
    "probe_every_s": 10.0,
    "refreshing": true,
    "last_refresh": {
      "outcome": "succeeded",
      "message": null,
      "reset_at": null,
      "at": "2026-09-17T12:00:00Z"
    },
    "total": 100,
    "repository_total": 102,
    "filter_totals": {
      "all": 102,
      "open": 100,
      "closed": 2
    },
    "count_at": "2026-09-17T12:00:00Z",
    "catalog_fetched": 102,
    "generation": "00000000000000000000000000000001:0",
    "fetched": 100,
    "complete": true,
    "truncated": false,
    "limit": 0,
    "next_after": null,
    "rows": []
  },
  "status_route": "/api/plugin/github/pulls?state=open&limit=0",
  "status_scan": "started"
}
after: /api/plugin/github/pulls?state=open&limit=0
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "list": "open",
  "fetched_at": "2026-09-17T12:00:00Z",
  "checked_at": null,
  "reader": "gh:someone-else",
  "fresh_for_s": 60.0,
  "probe_every_s": 10.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "gh_failed",
    "message": "gh exited 1 without an HTTP response",
    "reset_at": null,
    "at": "[TIMESTAMP]"
  },
  "total": 100,
  "repository_total": 102,
  "filter_totals": {
    "all": 102,
    "open": 100,
    "closed": 2
  },
  "count_at": "2026-09-17T12:00:00Z",
  "catalog_fetched": 102,
  "generation": "00000000000000000000000000000001:0",
  "fetched": 100,
  "complete": true,
  "truncated": false,
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
    "list": "open",
    "fetched_at": "2026-09-17T12:00:00Z",
    "checked_at": null,
    "reader": "gh:someone-else",
    "fresh_for_s": 60.0,
    "probe_every_s": 10.0,
    "refreshing": false,
    "last_refresh": {
      "outcome": "gh_failed",
      "message": "gh exited 1 without an HTTP response",
      "reset_at": null,
      "at": "[TIMESTAMP]"
    },
    "total": 100,
    "repository_total": 102,
    "filter_totals": {
      "all": 102,
      "open": 100,
      "closed": 2
    },
    "count_at": "2026-09-17T12:00:00Z",
    "catalog_fetched": 102,
    "generation": "00000000000000000000000000000001:0",
    "fetched": 100,
    "complete": true,
    "truncated": false,
    "limit": 0,
    "next_after": null,
    "rows": []
  },
  "status_route": "/api/plugin/github/pulls?state=open&limit=0",
  "status_scan": "not_due"
}
? 0
```
