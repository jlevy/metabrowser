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
  BUILD: '[0-9a-f]{12}'
  STORE: '[0-9a-f]{16}'
before: >-
  METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --files
  > fixture.log 2>&1 &&
  printf '{"number": 106}\n' > refresh-106.json &&
  printf '{"number": 7, "retry": true}\n' > retry-7.json &&
  printf '{"number": "7"}\n' > bad-number.json &&
  mkdir folder
---
# Golden tests: a pull request’s changed files from the cache

`tests/github_pull_fixture.py --files` builds `home` before these commands run: a mirror
of `https://github.com/octo/demo`, the records of pull requests 7 to 10, and, each
listed through `POST /api/plugin/github/pull-files-refresh` with a fake `gh` and a clock
fixed at 2026-09-17T12:00:00Z, these lists of changed files:

| Pull request | Listed from | Held |
| --- | --- | --- |
| 7 | The local comparison of its record | 2 files, with no `gh` |
| 106 | GitHub’s three pages | 249 files: a folder chain, renames, a deleted and a binary file, two names the display rule changes |
| 105 | GitHub’s thirty pages | 3,000 files, where GitHub stops listing |
| 104 | GitHub, stopped at its third page by the rate limit | 200 files of three pages |
| 103 | GitHub, as another account read it | 2 files, and a later refresh as this account failed |
| 12, 13 | Nothing usable | Another schema’s list, and one that is not JSON |

Every command below answers from that cache, and none reaches the network.
`gh` is `tests/fixtures/github-pull/no-gh/gh`, which fails every command, so a read that
asked it would show.
These lists are weeks old and still `current`: a list from GitHub is current while the
pull request’s `updated_at` is no newer than the list, and one from the local comparison
while the record’s base and head match the list’s. Refreshes that complete, each typed
failure, and a force-push are in `tests/golden/cli-github-pull-files-refresh.txt` and
`tests/golden/cli-github-pull-files-failures.txt`.

## Test: a pull request the mirror holds is listed from its local comparison

`listed_from` is `comparison`, `base` and `head` identify the comparison, and no
`reader`, since no account read it.
A row keeps the path, the path before a rename, GitHub’s status, and the line counts;
`display` is the path as it is painted.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=7'
api: /api/plugin/github/pull-files?number=7
status: 200
{
  "state": "current",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 7,
  "listed_from": "comparison",
  "fetched_at": "2026-09-17T12:00:00Z",
  "generation": "00000000000000000000000000000001",
  "reader": null,
  "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
  "base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 2,
  "pages": 0,
  "last_page": null,
  "complete": true,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 3000,
  "rows": [
    {
      "path": "docs/new.md",
      "previous_path": null,
      "status": "added",
      "additions": 1,
      "deletions": 0,
      "display": "docs/new.md",
      "previous_display": null
    },
    {
      "path": "src/app.txt",
      "previous_path": null,
      "status": "modified",
      "additions": 1,
      "deletions": 0,
      "display": "src/app.txt",
      "previous_display": null
    }
  ]
}
? 0
```

## Test: a list from GitHub, a window of its rows at a time

`fetched` is how many rows are held, `pages` how many of GitHub’s pages were read, and
`last_page` the count the first page’s `Link` header gave, which counts pages, not
files. `offset` and `limit` choose the rows; `limit=0` answers the envelope alone.
A rename keeps the old path in `previous_path`.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=106&limit=4'
api: /api/plugin/github/pull-files?number=106&limit=4
status: 200
{
  "state": "current",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 106,
  "listed_from": "github",
  "fetched_at": "2026-09-17T12:00:00Z",
  "generation": "00000000000000000000000000000002",
  "reader": "gh:octo-reader",
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 249,
  "pages": 3,
  "last_page": 3,
  "complete": true,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 4,
  "rows": [
    {
      "path": "README.md",
      "previous_path": null,
      "status": "modified",
      "additions": 2,
      "deletions": 1,
      "display": "README.md",
      "previous_display": null
    },
    {
      "path": "assets/logo.png",
      "previous_path": null,
      "status": "modified",
      "additions": 0,
      "deletions": 0,
      "display": "assets/logo.png",
      "previous_display": null
    },
    {
      "path": "docs/guide.md",
      "previous_path": "docs/old-guide.md",
      "status": "renamed",
      "additions": 3,
      "deletions": 0,
      "display": "docs/guide.md",
      "previous_display": "docs/old-guide.md"
    },
    {
      "path": "docs/removed.md",
      "previous_path": null,
      "status": "removed",
      "additions": 0,
      "deletions": 12,
      "display": "docs/removed.md",
      "previous_display": null
    }
  ]
}
? 0
```

## Test: a name is displayed through the pinned tree’s rule, and its path stays the identity

`weird/bell<BEL>name.txt` and `weird/zero<ZWSP>width.md` keep their characters in
`path`, which is what an address and the diff’s jump are given, and show U+FFFD in
`display`.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=106&offset=246'
api: /api/plugin/github/pull-files?number=106&offset=246
status: 200
{
  "state": "current",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 106,
  "listed_from": "github",
  "fetched_at": "2026-09-17T12:00:00Z",
  "generation": "00000000000000000000000000000002",
  "reader": "gh:octo-reader",
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 249,
  "pages": 3,
  "last_page": 3,
  "complete": true,
  "capped": false,
  "truncated": false,
  "offset": 246,
  "limit": 3000,
  "rows": [
    {
      "path": "tools/new/script.sh",
      "previous_path": "scripts/script.sh",
      "status": "renamed",
      "additions": 0,
      "deletions": 0,
      "display": "tools/new/script.sh",
      "previous_display": "scripts/script.sh"
    },
    {
      "path": "weird/bell\u0007name.txt",
      "previous_path": null,
      "status": "added",
      "additions": 1,
      "deletions": 0,
      "display": "weird/bell�name.txt",
      "previous_display": null
    },
    {
      "path": "weird/zero​width.md",
      "previous_path": null,
      "status": "modified",
      "additions": 1,
      "deletions": 1,
      "display": "weird/zero�width.md",
      "previous_display": null
    }
  ]
}
? 0
```

## Test: GitHub stops listing at 3,000 files, and the list says so

`capped` is true: the thirtieth page was full and named no next page, so the pull
request may have more files than GitHub lists.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=105&limit=0'
api: /api/plugin/github/pull-files?number=105&limit=0
status: 200
{
  "state": "current",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 105,
  "listed_from": "github",
  "fetched_at": "2026-09-17T12:00:00Z",
  "generation": "00000000000000000000000000000003",
  "reader": "gh:octo-reader",
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 3000,
  "pages": 30,
  "last_page": 30,
  "complete": true,
  "capped": true,
  "truncated": false,
  "offset": 0,
  "limit": 0,
  "rows": []
}
? 0
```

## Test: a list that stopped part-way keeps the pages it published

GitHub’s rate limit refused the third page.
The two pages before it were published as they arrived, so the list holds 200 files,
`complete` is false, and `last_page` says there were three pages; `last_refresh` says
why it stopped.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=104&limit=0'
api: /api/plugin/github/pull-files?number=104&limit=0
status: 200
{
  "state": "current",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 104,
  "listed_from": "github",
  "fetched_at": "2026-09-17T12:00:00Z",
  "generation": "00000000000000000000000000000004",
  "reader": "gh:octo-reader",
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "rate_limited",
    "message": "GitHub's API rate limit is exhausted until 2026-09-23T16:46:00Z",
    "reset_at": "2026-09-23T16:46:00Z",
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 200,
  "pages": 2,
  "last_page": 3,
  "complete": false,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 0,
  "rows": []
}
? 0
```

## Test: a list another account read is shown as it is, labelled with its reader

The last refresh ran as `octo-reader` and failed, so the list `someone-else` read stays,
`stale` although nothing about the pull request is newer.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=103'
api: /api/plugin/github/pull-files?number=103
status: 200
{
  "state": "stale",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 103,
  "listed_from": "github",
  "fetched_at": "2026-09-17T12:00:00Z",
  "generation": "00000000000000000000000000000005",
  "reader": "gh:someone-else",
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "network_error",
    "message": "gh could not reach api.github.com",
    "reset_at": null,
    "at": "2026-09-17T12:00:00Z"
  },
  "fetched": 2,
  "pages": 1,
  "last_page": null,
  "complete": true,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 3000,
  "rows": [
    {
      "path": "README.md",
      "previous_path": null,
      "status": "modified",
      "additions": 2,
      "deletions": 1,
      "display": "README.md",
      "previous_display": null
    },
    {
      "path": "assets/logo.png",
      "previous_path": null,
      "status": "modified",
      "additions": 0,
      "deletions": 0,
      "display": "assets/logo.png",
      "previous_display": null
    }
  ]
}
? 0
```

## Test: a list nothing has fetched is absent, and a read does not fetch it

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=9'
api: /api/plugin/github/pull-files?number=9
status: 200
{
  "state": "absent",
  "reason": "not_cached",
  "source": "https://github.com/octo/demo",
  "number": 9,
  "listed_from": null,
  "fetched_at": null,
  "generation": null,
  "reader": null,
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": null,
  "fetched": 0,
  "pages": 0,
  "last_page": null,
  "complete": false,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 3000,
  "rows": []
}
? 0
```
```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=12&limit=0'
api: /api/plugin/github/pull-files?number=12&limit=0
status: 200
{
  "state": "absent",
  "reason": "schema_mismatch",
  "source": "https://github.com/octo/demo",
  "number": 12,
  "listed_from": null,
  "fetched_at": null,
  "generation": null,
  "reader": null,
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": null,
  "fetched": 0,
  "pages": 0,
  "last_page": null,
  "complete": false,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 0,
  "rows": []
}
? 0
```
```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=13&limit=0'
api: /api/plugin/github/pull-files?number=13&limit=0
status: 200
{
  "state": "absent",
  "reason": "unreadable",
  "source": "https://github.com/octo/demo",
  "number": 13,
  "listed_from": null,
  "fetched_at": null,
  "generation": null,
  "reader": null,
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": null,
  "fetched": 0,
  "pages": 0,
  "last_page": null,
  "complete": false,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 0,
  "rows": []
}
? 0
```

## Test: a request the route cannot answer is refused

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pull-files
api: /api/plugin/github/pull-files
status: 400
{
  "error": "\"number\" is a pull-request number",
  "code": "invalid_request"
}
Error: /api/plugin/github/pull-files returned HTTP 400
? 1
```
```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/plugin/github/pull-files?number=7&limit=3001'
api: /api/plugin/github/pull-files?number=7&limit=3001
status: 400
{
  "error": "\"limit\" is a whole number from 0 to 3000",
  "code": "invalid_request"
}
Error: /api/plugin/github/pull-files?number=7&limit=3001 returned HTTP 400
? 1
```
```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pull-files-refresh --data bad-number.json
api: /api/plugin/github/pull-files-refresh
status: 400
{
  "error": "\"number\" is a pull-request number",
  "code": "invalid_request"
}
Error: /api/plugin/github/pull-files-refresh returned HTTP 400
? 1
```

## Test: one changed file’s address is the page’s Files changed, and the list says whether it holds it

A file row in the Pulls tab is a link to `/pull/<n>/files/<path>`, the path spelled one
percent-encoded segment at a time.
`--show` reports the page the shell mounts there, `pull-request` on its Files changed
tab, and what the cached list of changed files says of that path: whether it is listed,
with GitHub’s status, or not.
The path is a name in the comparison and nothing on disk: no file of the served tree is
read, and a path the list lacks is reported, not refused.
A name the display rule changes is printed as it is painted.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show /pull/7/files/docs/new.md
show: /pull/7/files/docs/new.md
route: /pull/7/files/docs/new.md
kind: pull-request
views: pull-request (default)
model: pull envelope; state=stale pull_state=open fetched_at=2026-09-17T12:00:00Z reader=gh:octo-reader issue_comments=1 reviews=2 review_comments=2 check_runs=2 statuses=1 tab=files comparison_route=/api/plugin/github/pull-comparison?number=7&left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=85fcb2fa9e77eb5db485ffef445cbbc645d6db4a&base_policy=merge_base&build=[BUILD]&store=[STORE]; file=docs/new.md file_list=current listed=added complete=True
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show /pull/106/files/weird/bell%07name.txt
show: /pull/106/files/weird/bell%07name.txt
route: /pull/106/files/weird/bell%07name.txt
kind: pull-request
views: pull-request (default)
model: pull envelope; state=absent reason=not_cached tab=files comparison_route=None; file=weird/bell�name.txt file_list=current listed=added complete=True
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show /pull/7/files/no/such/file.py
show: /pull/7/files/no/such/file.py
route: /pull/7/files/no/such/file.py
kind: pull-request
views: pull-request (default)
model: pull envelope; state=stale pull_state=open fetched_at=2026-09-17T12:00:00Z reader=gh:octo-reader issue_comments=1 reviews=2 review_comments=2 check_runs=2 statuses=1 tab=files comparison_route=/api/plugin/github/pull-comparison?number=7&left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=85fcb2fa9e77eb5db485ffef445cbbc645d6db4a&base_policy=merge_base&build=[BUILD]&store=[STORE]; file=no/such/file.py file_list=current listed=no complete=True
? 0
```

A pull request with no list of files says so, and a read does not fetch one.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show /pull/9/files/docs/new.md
show: /pull/9/files/docs/new.md
route: /pull/9/files/docs/new.md
kind: pull-request
views: pull-request (default)
model: pull envelope; state=stale pull_state=closed fetched_at=2026-09-17T12:00:00Z reader=gh:octo-reader issue_comments=0 reviews=0 review_comments=0 check_runs=2 statuses=1 tab=files comparison_route=/api/plugin/github/pull-comparison?number=9&left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd&base_policy=merge_base&build=[BUILD]&store=[STORE]; file=docs/new.md file_list=absent file_list_reason=not_cached
? 0
```

A path that is not a normalized one is not an address of this grammar.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --show /pull/7/files/docs/../new.md
Error: /pull/7/files/docs/../new.md is not a route this grammar accepts
? 1
```

## Test: a folder has no repository to list

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab folder --api '/api/plugin/github/pull-files?number=7&limit=0'
api: /api/plugin/github/pull-files?number=7&limit=0
status: 200
{
  "state": "absent",
  "reason": "not_github",
  "source": null,
  "number": 7,
  "listed_from": null,
  "fetched_at": null,
  "generation": null,
  "reader": null,
  "head": null,
  "base": null,
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": null,
  "fetched": 0,
  "pages": 0,
  "last_page": null,
  "complete": false,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 0,
  "rows": []
}
? 0
```
```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab folder --api /api/plugin/github/pull-files-refresh --data retry-7.json
api: /api/plugin/github/pull-files-refresh
status: 409
{
  "error": "this server serves no GitHub repository",
  "code": "not_github"
}
Error: /api/plugin/github/pull-files-refresh returned HTTP 409
? 1
```

## Test: a refresh from the local comparison needs no `gh`

A reader’s **Retry** on pull request 7 lists the comparison again from the store, with
the `gh` that fails every command first on `PATH`, and the command exits 0. The fixture
delegates these same arguments to the real CLI, pinning only this test process’s refresh
UUID; its new generation differs from the cached one.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" --files-refresh https://github.com/octo/demo --api /api/plugin/github/pull-files-refresh --data retry-7.json
api: /api/plugin/github/pull-files-refresh
status: 202
{
  "refresh": "started",
  "files": {
    "state": "current",
    "reason": null,
    "source": "https://github.com/octo/demo",
    "number": 7,
    "listed_from": "comparison",
    "fetched_at": "2026-09-17T12:00:00Z",
    "generation": "00000000000000000000000000000001",
    "reader": null,
    "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
    "base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
    "fresh_for_s": 60.0,
    "refreshing": true,
    "last_refresh": {
      "outcome": "succeeded",
      "message": null,
      "reset_at": null,
      "at": "2026-09-17T12:00:00Z"
    },
    "fetched": 2,
    "pages": 0,
    "last_page": null,
    "complete": true,
    "capped": false,
    "truncated": false,
    "offset": 0,
    "limit": 0,
    "rows": []
  },
  "status_route": "/api/plugin/github/pull-files?number=7&limit=0"
}
after: /api/plugin/github/pull-files?number=7&limit=0
status: 200
{
  "state": "current",
  "reason": null,
  "source": "https://github.com/octo/demo",
  "number": 7,
  "listed_from": "comparison",
  "fetched_at": "[TIMESTAMP]",
  "generation": "0000000000000000000000000000000f",
  "reader": null,
  "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a",
  "base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
  "fresh_for_s": 60.0,
  "refreshing": false,
  "last_refresh": {
    "outcome": "succeeded",
    "message": null,
    "reset_at": null,
    "at": "[TIMESTAMP]"
  },
  "fetched": 2,
  "pages": 0,
  "last_page": null,
  "complete": true,
  "capped": false,
  "truncated": false,
  "offset": 0,
  "limit": 0,
  "rows": []
}
? 0
```

## Test: a refresh from GitHub returns at once, and the command says how it ended

Pull request 106’s list is current, so expanding its row starts nothing: `not_due`.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api /api/plugin/github/pull-files-refresh --data refresh-106.json
api: /api/plugin/github/pull-files-refresh
status: 200
{
  "refresh": "not_due",
  "files": {
    "state": "current",
    "reason": null,
    "source": "https://github.com/octo/demo",
    "number": 106,
    "listed_from": "github",
    "fetched_at": "2026-09-17T12:00:00Z",
    "generation": "00000000000000000000000000000002",
    "reader": "gh:octo-reader",
    "head": null,
    "base": null,
    "fresh_for_s": 60.0,
    "refreshing": false,
    "last_refresh": {
      "outcome": "succeeded",
      "message": null,
      "reset_at": null,
      "at": "2026-09-17T12:00:00Z"
    },
    "fetched": 249,
    "pages": 3,
    "last_page": 3,
    "complete": true,
    "capped": false,
    "truncated": false,
    "offset": 0,
    "limit": 0,
    "rows": []
  },
  "status_route": "/api/plugin/github/pull-files?number=106&limit=0"
}
? 0
```
