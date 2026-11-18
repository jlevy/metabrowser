---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "ERROR"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  PYTHONPATH="$TRYSCRIPT_TEST_DIR/../.."
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python -m tests.source_checkout_fixture .
  > fixture.log 2>&1 && mkdir plain
---
# Golden tests: a checkout’s refs, revisions, and working tree through `--api`

`tests/source_checkout_fixture.py` builds `checkout`, a clone of the fixture origin
`tests/source_mirror_fixture.py` writes with `git fast-import`, so each commit ID below
is the same on every machine: `topic` is `first` (`fcb9d63c3…`) then `second`
(`42382ea…`), `feature` (`c7ae2a3…`) branches from `first`, and `v1` is an annotated tag
of `first`. The checkout is on `topic` and adds what only a checkout has: a branch
`local-work` with a commit no remote holds, the remote-tracking branches `origin/topic`
and `origin/feature`, a lightweight tag `local-tag`, and a working tree that is not any
commit: `README.md` edited and not staged, `STAGED.md` in the index and not committed,
and `UNTRACKED.md` on disk only.

A folder that is a repository’s root is in folder mode, which is a superset of mirror
mode: a branch or tag is shown as a mirror shows one, a pinned revision read from the
checkout’s Git objects, and the working tree is a separate choice, the one the folder
opens on. Each command is its own process, so a switch lasts for that command only, and
every command starts on the working tree.

## Test: a folder opens on its working tree

No pin and no ref: the subject is the folder.

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/status
api: /api/source/status
status: 200
{
  "subject": "attached_filesystem",
  "generation": 1,
  "pin": null,
  "ref": null,
  "ref_name": null,
  "name": null,
  "origin": null,
  "location": null,
  "borrows": null,
  "shallow": false,
  "refreshable": false,
  "latest": null,
  "ref_on_origin": null,
  "last_fetch_at": null,
  "last_outcome": null,
  "refreshing": false,
  "stale": false,
  "pull_request": null,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: the selector lists the working tree and the checkout’s own branches

`working_tree` says the working tree is what is served and which branch is checked out.
`kinds` names the three lists a checkout has.
The checked-out branch lists first and is `checked_out`, not `current`: chosen as a ref
it shows its commit, which the working tree is not.

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/refs
api: /api/source/refs
status: 200
{
  "kind": "branch",
  "query": "",
  "limit": 100,
  "pin": null,
  "ref": null,
  "kinds": [
    "branch",
    "tag",
    "remote"
  ],
  "working_tree": {
    "current": true,
    "head": "refs/heads/topic",
    "head_name": "topic"
  },
  "total": 3,
  "truncated": false,
  "refs": [
    {
      "name": "topic",
      "ref": "refs/heads/topic",
      "commit": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "default": false,
      "checked_out": true,
      "current": false
    },
    {
      "name": "feature",
      "ref": "refs/heads/feature",
      "commit": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
      "default": false,
      "checked_out": false,
      "current": false
    },
    {
      "name": "local-work",
      "ref": "refs/heads/local-work",
      "commit": "25e0a2a76ab47a407f3dee083221e6efdcca6283",
      "default": false,
      "checked_out": false,
      "current": false
    }
  ]
}
? 0
```

## Test: remote-tracking branches are a third list

Each keeps its remote’s name.
The symbolic `origin/HEAD` a clone writes is not a row: it names `origin/topic`.

```console
$ metab --cache-dir home --config-dir config checkout --api '/api/source/refs?kind=remote'
api: /api/source/refs?kind=remote
status: 200
{
  "kind": "remote",
  "query": "",
  "limit": 100,
  "pin": null,
  "ref": null,
  "kinds": [
    "branch",
    "tag",
    "remote"
  ],
  "working_tree": {
    "current": true,
    "head": "refs/heads/topic",
    "head_name": "topic"
  },
  "total": 2,
  "truncated": false,
  "refs": [
    {
      "name": "origin/feature",
      "ref": "refs/remotes/origin/feature",
      "commit": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
      "default": false,
      "checked_out": false,
      "current": false
    },
    {
      "name": "origin/topic",
      "ref": "refs/remotes/origin/topic",
      "commit": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "default": false,
      "checked_out": false,
      "current": false
    }
  ]
}
? 0
```

## Test: tags list newest first, peeled to the commit they name

```console
$ metab --cache-dir home --config-dir config checkout --api '/api/source/refs?kind=tag'
api: /api/source/refs?kind=tag
status: 200
{
  "kind": "tag",
  "query": "",
  "limit": 100,
  "pin": null,
  "ref": null,
  "kinds": [
    "branch",
    "tag",
    "remote"
  ],
  "working_tree": {
    "current": true,
    "head": "refs/heads/topic",
    "head_name": "topic"
  },
  "total": 2,
  "truncated": false,
  "refs": [
    {
      "name": "local-tag",
      "ref": "refs/tags/local-tag",
      "commit": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
      "default": false,
      "checked_out": false,
      "current": false
    },
    {
      "name": "v1",
      "ref": "refs/tags/v1",
      "commit": "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e",
      "default": false,
      "checked_out": false,
      "current": false
    }
  ]
}
? 0
```

## Test: a branch is served as a revision of the checkout

The subject becomes a pinned revision named as the folder is, with no origin and nothing
to refresh, since nothing is fetched into a checkout.
`location` is the checkout, whose Git objects the pages are read from.
The page was on the folder’s `README.md`; `view_href` is that file at the revision’s
address.

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-feature-view.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref": "refs/heads/feature",
    "ref_name": "feature",
    "name": "checkout",
    "origin": null,
    "location": "<ROOT>",
    "borrows": null,
    "shallow": false,
    "refreshable": false,
    "latest": null,
    "ref_on_origin": null,
    "last_fetch_at": null,
    "last_outcome": null,
    "refreshing": false,
    "stale": false,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  },
  "view_href": "/view/g1-UkVBRE1FLm1k"
}
? 0
```

## Test: the checked-out branch is its last commit, not the working tree

`STAGED.md` is in the index and in no commit, so a page on it goes to the root.

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-checked-out.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "ref": "refs/heads/topic",
    "ref_name": "topic",
    "name": "checkout",
    "origin": null,
    "location": "<ROOT>",
    "borrows": null,
    "shallow": false,
    "refreshable": false,
    "latest": null,
    "ref_on_origin": null,
    "last_fetch_at": null,
    "last_outcome": null,
    "refreshing": false,
    "stale": false,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  },
  "view_href": "/view/"
}
? 0
```

## Test: a remote-tracking branch and a tag are served by name

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-remote.json
api: /api/source/pin
status: 200
{
  "changed": true,
  "status": {
    "subject": "git_revision",
    "generation": 2,
    "pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
    "ref": "refs/remotes/origin/feature",
    "ref_name": "origin/feature",
    "name": "checkout",
    "origin": null,
    "location": "<ROOT>",
    "borrows": null,
    "shallow": false,
    "refreshable": false,
    "latest": null,
    "ref_on_origin": null,
    "last_fetch_at": null,
    "last_outcome": null,
    "refreshing": false,
    "stale": false,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  }
}
? 0
```

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-tag.json
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
    "name": "checkout",
    "origin": null,
    "location": "<ROOT>",
    "borrows": null,
    "shallow": false,
    "refreshable": false,
    "latest": null,
    "ref_on_origin": null,
    "last_fetch_at": null,
    "last_outcome": null,
    "refreshing": false,
    "stale": false,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  }
}
? 0
```

## Test: the working tree is asked for by name

It is already served in a new process, so nothing changes.

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-working-tree.json
api: /api/source/pin
status: 200
{
  "changed": false,
  "status": {
    "subject": "attached_filesystem",
    "generation": 1,
    "pin": null,
    "ref": null,
    "ref_name": null,
    "name": null,
    "origin": null,
    "location": null,
    "borrows": null,
    "shallow": false,
    "refreshable": false,
    "latest": null,
    "ref_on_origin": null,
    "last_fetch_at": null,
    "last_outcome": null,
    "refreshing": false,
    "stale": false,
    "pull_request": null,
    "selection_state": null,
    "selection_href": null
  }
}
? 0
```

## Test: a ref the checkout lacks is not found, and nothing is fetched

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-gone.json
api: /api/source/pin
status: 404
{
  "error": "no branch or tag with that name is in the checkout",
  "code": "selection_not_found"
}
Error: /api/source/pin returned HTTP 404
? 1
```

## Test: revision syntax and a mixed selection are refused before any lookup

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-syntax.json
api: /api/source/pin
status: 400
{
  "error": "the ref is not a valid Git ref name",
  "code": "invalid_selection"
}
Error: /api/source/pin returned HTTP 400
? 1
```

```console
$ metab --cache-dir home --config-dir config checkout --api /api/source/pin --data pin-working-tree-and-ref.json
api: /api/source/pin
status: 400
{
  "error": "\"working_tree\" is true, alone or with \"view\"",
  "code": "invalid_selection"
}
Error: /api/source/pin returned HTTP 400
? 1
```

## Test: a window of a checkout is called by its folder

```console
$ metab --cache-dir home --config-dir config checkout --api /api/identity
api: /api/identity
status: 200
{
  "short_name": "checkout",
  "full_name": "<ROOT>",
  "kind": "folder",
  "kind_label": "Local folder",
  "title": "checkout • Metabrowser"
}
? 0
```

## Test: `--ref` opens the folder on a branch

`metab PATH --ref NAME` starts on a revision where `metab PATH` starts on the working
tree, by the switch the selector makes: the subject is the pin, named by the folder.

```console
$ metab --cache-dir home --config-dir config checkout --ref feature --api /api/source/status
api: /api/source/status
status: 200
{
  "subject": "git_revision",
  "generation": 2,
  "pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b",
  "ref": "refs/heads/feature",
  "ref_name": "feature",
  "name": "checkout",
  "origin": null,
  "location": "<ROOT>",
  "borrows": null,
  "shallow": false,
  "refreshable": false,
  "latest": null,
  "ref_on_origin": null,
  "last_fetch_at": null,
  "last_outcome": null,
  "refreshing": false,
  "stale": false,
  "pull_request": null,
  "selection_state": null,
  "selection_href": null
}
? 0
```

## Test: a revision’s files are read by the routes a page reads them by

`feature` has `FEATURE.md` and the committed `README.md`, and none of the working tree’s
edited, staged, or untracked files.
The catalog is every file of the revision, each named by its `GitPath` wire (`p`), as on
a mirror.

```console
$ metab --cache-dir home --config-dir config checkout --ref feature --api /api/catalog
api: /api/catalog
status: 200
{
  "complete": true,
  "truncated": false,
  "revision": 1,
  "files": [
    {
      "p": "g1-RkVBVFVSRS5tZA",
      "e": ".md",
      "n": "FEATURE.md"
    },
    {
      "p": "g1-UkVBRE1FLm1k",
      "e": ".md",
      "n": "README.md"
    }
  ]
}
? 0
```

```console
$ metab --cache-dir home --config-dir config checkout --ref feature --show FEATURE.md
show: FEATURE.md
route: /view/g1-RkVBVFVSRS5tZA
kind: markdown
views: rendered (default, key V), source (key S)
model: text envelope; size=17 content_bytes=17 content_truncated=False
? 0
```

## Test: `--ref` takes a tag, a remote-tracking branch, and a commit ID

A window of a revision is still called by its folder, and its full name adds what is
shown. The home directory is set to the sandbox here, so the folder’s path is spelled as
a reader’s is, with `~`.

```console
$ HOME=$PWD metab --cache-dir home --config-dir config checkout --ref v1 --api /api/identity
api: /api/identity
status: 200
{
  "short_name": "checkout",
  "full_name": "~/checkout@v1",
  "kind": "folder",
  "kind_label": "Local folder",
  "title": "checkout • Metabrowser"
}
? 0
```

```console
$ HOME=$PWD metab --cache-dir home --config-dir config checkout --ref origin/feature --api /api/identity
api: /api/identity
status: 200
{
  "short_name": "checkout",
  "full_name": "~/checkout@origin/feature",
  "kind": "folder",
  "kind_label": "Local folder",
  "title": "checkout • Metabrowser"
}
? 0
```

```console
$ metab --cache-dir home --config-dir config checkout --ref fcb9d63c3c85 --show README.md
show: README.md
route: /view/g1-UkVBRE1FLm1k
kind: markdown
views: rendered (default, key V), source (key S)
model: text envelope; size=9 content_bytes=9 content_truncated=False
? 0
```

## Test: the navigation check runs on a revision

A revision has no recency, so the live filter answers its typed refusal, which is what a
page hides that filter by.

```console
$ metab --cache-dir home --config-dir config checkout --ref feature --check-api
api check: checkout
scenario: nav-live-clear-filter
initial tree: 200; response=tree
live filter: 409; unsupported_for_subject
cleared filter: 200; response=tree
index: done
final nav: 200; rows=2; files=2; size=26; index=done
filtered nav: 200; rows=2; files=2; size=26; empty_dirs=0
result: pass
? 0
```

## Test: a ref the checkout lacks, revision syntax, and a root with no checkout are refused

Nothing is fetched for a name the checkout does not have, and nothing starts.

```console
$ metab --cache-dir home --config-dir config checkout --ref gone --api /api/source/status
Error: --ref gone: no branch or tag with that name is in the checkout
? 1
```

```console
$ metab --cache-dir home --config-dir config checkout --ref 'topic~1' --show README.md
Error: --ref topic~1: the ref is not a valid Git ref name
? 1
```

```console
$ metab --cache-dir home --config-dir config plain --ref feature --api /api/source/status
Error: --ref names a branch or tag of a checkout, and ROOT is not a Git repository's root
? 1
```

A Git source names its branch or tag in its URL.

```console
$ metab --cache-dir home --config-dir config file://$PWD/origin.git --ref feature --api /api/source/status
Error: --ref names a branch or tag of a local checkout, and ROOT is a Git source; name the branch or tag in the URL
? 1
```

## Test: a plain folder has no refs to choose among

```console
$ metab --cache-dir home --config-dir config plain --api /api/source/refs
api: /api/source/refs
status: 409
{
  "error": "source does not support refs",
  "code": "unsupported_for_subject",
  "capability": "refs"
}
Error: /api/source/refs returned HTTP 409
? 1
```

## Test: none of it wrote the checkout

After every command above, `HEAD`, the index, and the working tree are what the fixture
left: on `topic`, with `README.md` modified and not staged, `STAGED.md` added, and
`UNTRACKED.md` untracked.
`tests/test_checkout_revisions.py` compares every file under the checkout, its `.git`
included, byte for byte.

```console
$ git -C checkout status --porcelain=v1 --branch
## topic...origin/topic
 M README.md
A  STAGED.md
?? UNTRACKED.md
? 0
```

```console
$ git -C checkout rev-parse HEAD
42382ea2303b733e1e21b4bd6ddb974ca4e775eb
? 0
```
