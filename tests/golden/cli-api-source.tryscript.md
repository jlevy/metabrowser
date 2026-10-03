---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "ERROR"
patterns:
  TIMESTAMP: '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'
  APP_HOME: '[^\s"]+/home'
  STORE_KEY: '[0-9a-f]{64}'
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../source_mirror_fixture.py" .
  --hold-fetch-lock > fixture.log 2>&1
after: kill "$(cat holder.pid)" 2>/dev/null || true
---
# Golden tests: a served mirror’s status, refs, refresh, and pin through `--api`

`tests/source_mirror_fixture.py` writes a bare `origin.git` with `git fast-import`, so
every identity and date is fixed and each commit ID below is the same on every machine:
`topic`, the default branch, is `first` (`fcb9d63c3…`) then `second` (`42382ea…`);
`feature` (`c7ae2a3…`) branches from `first`; `v1` is an annotated tag of `first`. The
fixture acquires that origin into `home` and records its last fetch at a fixed time, so
each command here opens the cached store as a mirror and serves the default branch.

A one-shot `--api` serves the mirror but never refreshes it on its own, which is why the
old fetch still reads `stale` here.
Each command is its own process, so a pin switch lasts for that command only.

## Test: status reports the pin and the mirror’s freshness

`latest` is the commit the pinned ref names in the mirror now; it equals the pin until a
refresh moves the ref.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/status
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "ref_name": "topic",
  "name": "origin",
  "origin": "file://[CWD]/origin.git",
  "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
  "refreshable": true,
  "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref_on_origin": true,
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
}
? 0
```

## Test: status names the repository and says where its mirror is kept

`name` is what a checkout of the origin would be called, `origin` the address it
mirrors, and `location` the store’s bare Git repository, which every page is read from.
A page’s headings show all three where a folder’s show its name and path.

In every other command of this transcript the application home is outside the home
directory, so the location is absolute, and `--api` prints it as the route answered it.
Here the home directory is set to the application home, so the location is spelled as a
reader’s is, with `~`. The origin is outside it and stays as given.
The store’s key is derived from the origin’s address, which is the sandbox’s.

```console
$ HOME=$PWD/home METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/status
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "ref_name": "topic",
  "name": "origin",
  "origin": "file://[CWD]/origin.git",
  "location": "~/cache/repository-stores/[STORE_KEY]/repository.git",
  "refreshable": true,
  "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref_on_origin": true,
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
}
? 0
```

## Test: pinning a branch

The branch resolves in the mirror, the served subject is replaced, and the generation
moves.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-feature.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref": "refs/remotes/origin/feature",
    "ref_name": "feature",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref_on_origin": true,
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
  }
}
? 0
```

## Test: pinning an annotated tag serves the commit it names

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-tag.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e",
    "ref": "refs/tags/v1",
    "ref_name": "v1",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e",
    "ref_on_origin": true,
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
  }
}
? 0
```

## Test: pinning an abbreviated commit ID

A commit pinned by ID that is not the tip of the ref served has no ref, so there is no
`latest` to compare with.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-oid.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e",
    "ref": null,
    "ref_name": null,
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
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
  }
}
? 0
```

## Test: a commit ID that is the tip of the ref served keeps the ref

View file on a diff switches by commit ID. A commit that is the tip of the ref the
server was serving is served under that ref, so a reader who went to another commit and
came back by ID is on the branch again, with a `latest` to compare with.
Here the ID is the served branch’s own tip, so nothing changes.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-tip-oid.json
api: /api/source/pin
status: 200
{
  "changed": false,
  "status": {
    "subject": "git_revision",
    "generation": 1,
    "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref": "refs/remotes/origin/topic",
    "ref_name": "topic",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref_on_origin": true,
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
  }
}
? 0
```

## Test: pinning what is already served changes nothing

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-same.json
api: /api/source/pin
status: 200
{
  "changed": false,
  "status": {
    "subject": "git_revision",
    "generation": 1,
    "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref": "refs/remotes/origin/topic",
    "ref_name": "topic",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref_on_origin": true,
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
  }
}
? 0
```

## Test: a name the mirror does not have is not found

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-missing.json
api: /api/source/pin
status: 404
{
  "error": "no branch or tag with that name is in the mirror",
  "code": "selection_not_found"
}
Error: /api/source/pin returned HTTP 404
? 1
```

## Test: a commit the mirror does not have is named, and nothing is fetched

The commit route reads the mirror alone.
A commit ID no object in it has answers `commit_not_found`; the route is a GET, so it
starts no fetch, and a served page asks for one itself through
`POST /api/source/refresh`.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/git/commit/0123456789abcdef0123456789abcdef01234567
api: /api/git/commit/0123456789abcdef0123456789abcdef01234567
status: 404
{
  "error": "unknown revision",
  "code": "commit_not_found"
}
Error: /api/git/commit/0123456789abcdef0123456789abcdef01234567 returned HTTP 404
? 1
```

## Test: revision syntax is refused before any lookup

`:/first` would be a commit-message search to `rev-parse`; it is not a valid ref name,
and not a commit ID, so it never reaches Git.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-syntax.json
api: /api/source/pin
status: 400
{
  "error": "the ref is not a valid Git ref name",
  "code": "invalid_selection"
}
Error: /api/source/pin returned HTTP 400
? 1
```

## Test: the ref selector lists branches, the default first

`/api/source/refs` reads the mirror alone.
Branches list by name after the default branch; `current` marks the ref the server
serves.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/refs
api: /api/source/refs
status: 200
{
  "kind": "branch",
  "query": "",
  "limit": 100,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "total": 2,
  "truncated": false,
  "refs": [
    {
      "name": "topic",
      "ref": "refs/remotes/origin/topic",
      "commit": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "default": true,
      "current": true
    },
    {
      "name": "feature",
      "ref": "refs/remotes/origin/feature",
      "commit": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
      "default": false,
      "current": false
    }
  ]
}
? 0
```

## Test: tags list newest first, peeled to the commit they name

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api "/api/source/refs?kind=tag"
api: /api/source/refs?kind=tag
status: 200
{
  "kind": "tag",
  "query": "",
  "limit": 100,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "total": 1,
  "truncated": false,
  "refs": [
    {
      "name": "v1",
      "ref": "refs/tags/v1",
      "commit": "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e",
      "default": false,
      "current": false
    }
  ]
}
? 0
```

## Test: the filter is a case-insensitive name fragment, and a page can stop short

Both branches contain a `t`; the page holds one of them, so `truncated` is true.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api "/api/source/refs?q=T&limit=1"
api: /api/source/refs?q=T&limit=1
status: 200
{
  "kind": "branch",
  "query": "T",
  "limit": 1,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "total": 2,
  "truncated": true,
  "refs": [
    {
      "name": "topic",
      "ref": "refs/remotes/origin/topic",
      "commit": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "default": true,
      "current": true
    }
  ]
}
? 0
```

## Test: an unknown kind is refused

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api "/api/source/refs?kind=commit"
api: /api/source/refs?kind=commit
status: 400
{
  "error": "\"kind\" is \"branch\" or \"tag\"",
  "code": "invalid_request"
}
Error: /api/source/refs?kind=commit returned HTTP 400
? 1
```

## Test: a switch from the selector keeps the page where the new pin has it

The selector posts the full ref it listed and the page’s `/view/` address; `view_href`
is where the page goes.
`README.md` is on `feature`, so the page stays on it.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-feature-view.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref": "refs/remotes/origin/feature",
    "ref_name": "feature",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref_on_origin": true,
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
  "view_href": "/view/g1-UkVBRE1FLm1k"
}
? 0
```

## Test: a page the new pin lacks goes to the root

`NOTES.md` arrived in `second`, which `feature` does not contain.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/pin --data pin-feature-away.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref": "refs/remotes/origin/feature",
    "ref_name": "feature",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref_on_origin": true,
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
  "view_href": "/view/"
}
? 0
```

## Test: a refresh another process is running is reported, not waited on

The fixture holds the store’s fetch lock from another process, as a second server’s
refresh would. The request still starts a refresh and returns at once with the envelope
as it starts; the command then waits for the refresh it asked for and prints the status
after it. That refresh found the lock held, so it reports `refreshing_elsewhere` and
fetches nothing, and the command exits 0 because a refresh is under way.
The lock is tried before the installed Git is checked, so this answer is the same on
every machine; refreshes that fetch, and one that fails and exits 1, are recorded
in-process in `cli-git-refresh.txt`, because a transcript has to pass on a Git below the
floor a fetch requires.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/refresh --data refresh.json
api: /api/source/refresh
status: 202
{
  "refresh": "started",
  "status": {
    "subject": "git_revision",
    "generation": 1,
    "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref": "refs/remotes/origin/topic",
    "ref_name": "topic",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref_on_origin": true,
    "last_fetch_at": "2026-09-17T12:00:05Z",
    "last_outcome": {
      "operation": "acquire",
      "outcome": "succeeded",
      "at": "2026-09-17T12:00:05Z"
    },
    "refreshing": true,
    "stale": true,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  }
}
after: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "ref_name": "topic",
  "name": "origin",
  "origin": "file://[CWD]/origin.git",
  "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
  "refreshable": true,
  "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref_on_origin": true,
  "last_fetch_at": "2026-09-17T12:00:05Z",
  "last_outcome": {
    "operation": "refresh",
    "outcome": "refreshing_elsewhere",
    "at": "[TIMESTAMP]"
  },
  "refreshing": false,
  "stale": true,
  "pull_request": null,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: a commit’s fetch is asked for by name, and a stale mirror gets it

A page that opens a commit the mirror lacks posts `{"for": "commit"}`. A link in served
content can send a reader to such an address, so this request fetches the mirror only
when its last fetch is older than the freshness window, as this one’s is: the answer is
`started`. On a mirror fetched inside the window it is `fresh` and nothing starts, which
`cli-git-refresh.txt` records, since that takes a fetch.
The fetch lock is still held, so the fetch that started reports `refreshing_elsewhere`.

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/refresh --data commit-fetch.json
api: /api/source/refresh
status: 202
{
  "refresh": "started",
  "status": {
    "subject": "git_revision",
    "generation": 1,
    "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref": "refs/remotes/origin/topic",
    "ref_name": "topic",
    "name": "origin",
    "origin": "file://[CWD]/origin.git",
    "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
    "refreshable": true,
    "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref_on_origin": true,
    "last_fetch_at": "2026-09-17T12:00:05Z",
    "last_outcome": {
      "operation": "acquire",
      "outcome": "succeeded",
      "at": "2026-09-17T12:00:05Z"
    },
    "refreshing": true,
    "stale": true,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  }
}
after: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 1,
  "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref": "refs/remotes/origin/topic",
  "ref_name": "topic",
  "name": "origin",
  "origin": "file://[CWD]/origin.git",
  "location": "[APP_HOME]/cache/repository-stores/[STORE_KEY]/repository.git",
  "refreshable": true,
  "latest": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
  "ref_on_origin": true,
  "last_fetch_at": "2026-09-17T12:00:05Z",
  "last_outcome": {
    "operation": "refresh",
    "outcome": "refreshing_elsewhere",
    "at": "[TIMESTAMP]"
  },
  "refreshing": false,
  "stale": true,
  "pull_request": null,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: a refresh request that names anything else is refused

```console
$ METABROWSER_HOME=$PWD/home metab file://$PWD/origin.git --api /api/source/refresh --data refresh-branch.json
api: /api/source/refresh
status: 400
{
  "error": "\"for\" may only be \"commit\"",
  "code": "invalid_request"
}
Error: /api/source/refresh returned HTTP 400
? 1
```
