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
  METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" .
  > fixture.log 2>&1 &&
  mkdir -p checkout/docs checkout/src &&
  cd checkout &&
  git init -q --initial-branch=main . &&
  git remote add origin https://github.com/octo/demo.git &&
  printf '# Demo\n' > README.md &&
  printf '# Guide\n' > docs/guide.md &&
  printf 'Spaced.\n' > 'docs/a b.md' &&
  printf 'one\n' > src/app.txt &&
  printf 'build/\n*.log\n' > .gitignore &&
  git add -A &&
  git commit -q -m 'first commit' &&
  git update-ref refs/remotes/origin/trunk HEAD &&
  git checkout -q -b local-work &&
  printf 'Committed here, pushed nowhere.\n' > LOCAL.md &&
  git add LOCAL.md &&
  git commit -q -m 'local work' &&
  git checkout -q main &&
  printf 'Edited, not committed.\n' >> README.md &&
  printf 'Staged, not committed.\n' > docs/staged.md &&
  git add docs/staged.md &&
  printf 'On disk only.\n' > notes.txt &&
  mkdir scratch build &&
  printf 'On disk only.\n' > scratch/draft.md &&
  printf 'Built.\n' > build/out.bin &&
  printf 'Logged.\n' > debug.log &&
  cd .. &&
  git clone -q checkout ahead &&
  cd ahead &&
  git remote set-url origin https://github.com/octo/demo.git &&
  printf 'Ahead of origin.\n' > AHEAD.md &&
  git add AHEAD.md &&
  git commit -q -m 'ahead' &&
  printf 'Edited here.\n' >> docs/guide.md &&
  cd .. &&
  git clone -q checkout branch &&
  cd branch &&
  git remote set-url origin https://github.com/octo/demo.git &&
  git update-ref refs/remotes/origin/feature/docs HEAD &&
  git checkout -q -b local-docs --track origin/feature/docs &&
  cd .. &&
  git clone -q checkout topic &&
  cd topic &&
  git remote set-url origin https://github.com/octo/demo.git &&
  git checkout -q -b topic &&
  printf 'On a branch with no upstream.\n' > TOPIC.md &&
  git add TOPIC.md &&
  git commit -q -m 'topic' &&
  cd .. &&
  git clone -q checkout alone &&
  cd alone &&
  git remote set-url origin https://github.com/octo/demo.git &&
  git remote set-head origin -d &&
  git checkout -q -b alone &&
  printf 'No upstream, and no default branch of origin.\n' > ALONE.md &&
  git add ALONE.md &&
  git commit -q -m 'alone' &&
  cd .. &&
  mkdir elsewhere &&
  cd elsewhere &&
  git init -q --initial-branch=main . &&
  git remote add origin https://gitlab.com/octo/demo.git &&
  printf '# Elsewhere\n' > README.md &&
  git add README.md &&
  git commit -q -m 'elsewhere' &&
  cd .. &&
  mkdir plain &&
  printf '# Plain\n' > plain/README.md
---
# Golden tests: a page’s github.com counterpart through `--api`

`GET /api/counterpart?page=<page>` answers the github.com page that shows what a
Metabrowser page shows, which every page’s View on GitHub control links to, or `null`
and a reason (`src/metabrowser/counterpart.py`). `page` is the address as the browser’s
`location.pathname` spells it.

The fixture builds, with identity and dates fixed so each commit ID below is the same on
every machine:

- `checkout`, a repository whose `origin` is `https://github.com/octo/demo.git`. Its
  `main` (`6df6ba6…`) is what `refs/remotes/origin/trunk` names, as a fetch would have
  left it, and `local-work` has a commit no remote holds.
  Its working tree differs from `main`: `README.md` is edited, `docs/staged.md` is
  staged and not committed, `notes.txt` and `scratch/` are untracked, and `debug.log`
  and `build/` are ignored.
- `ahead`, a clone of `checkout` with the same `origin`, one commit past its upstream
  branch, with `docs/guide.md` edited.
- `branch`, a clone whose local `local-docs` branch tracks the origin’s `feature/docs`.
- `topic`, a clone on a branch with no upstream, one commit past the clone’s
  `origin/HEAD`.
- `alone`, the same with no `origin/HEAD` either.
- `elsewhere`, a repository whose `origin` is not on github.com, and `plain`, a folder.
- `home`, by `tests/github_pull_fixture.py`: a mirror of `https://github.com/octo/demo`
  with pull request 7’s head, which only `refs/pull/7/head` reaches.

No command reaches the network, and `gh` fails every command.

## Test: the working tree’s repository root opens the repository

HEAD’s commit is on origin, but its local branch does not name an origin branch.
The repository root opens the repository URL and its items open at the commit.
A folder is told by the commit’s tree, with or without a trailing slash, and untracked
and ignored files inside it do not stop it from mapping.

```console
$ metab checkout --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/docs/'
api: /api/counterpart?page=/view/docs/
status: 200
{
  "page": "/view/docs/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/src'
api: /api/counterpart?page=/view/src
status: 200
{
  "page": "/view/src",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/src"
  },
  "reason": null
}
? 0
```

## Test: a file at HEAD with no change maps to its blob

`page` is the address encoded once more, as `encodeURIComponent(location.pathname)`
sends it, so `a%2520b.md` names the page `…/a%20b.md`, which shows the file `a b.md`.
The counterpart encodes the path GitHub’s way.

```console
$ metab checkout --api '/api/counterpart?page=/view/docs/guide.md'
api: /api/counterpart?page=/view/docs/guide.md
status: 200
{
  "page": "/view/docs/guide.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs/guide.md"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/docs/a%2520b.md'
api: /api/counterpart?page=/view/docs/a%2520b.md
status: 200
{
  "page": "/view/docs/a%20b.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs/a%20b.md"
  },
  "reason": null
}
? 0
```

## Test: an edited file maps to the version origin has, and a staged one is uncommitted

`README.md` is edited, so its button links to the version origin has.
`docs/staged.md` is in the index only, so origin has no version of it.

```console
$ metab checkout --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/README.md"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/docs/staged.md'
api: /api/counterpart?page=/view/docs/staged.md
status: 200
{
  "page": "/view/docs/staged.md",
  "counterpart": null,
  "reason": "uncommitted"
}
? 0
```

## Test: untracked and ignored files and folders have no counterpart

A file inside an ignored folder is ignored too.

```console
$ metab checkout --api '/api/counterpart?page=/view/notes.txt'
api: /api/counterpart?page=/view/notes.txt
status: 200
{
  "page": "/view/notes.txt",
  "counterpart": null,
  "reason": "untracked"
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/scratch/'
api: /api/counterpart?page=/view/scratch/
status: 200
{
  "page": "/view/scratch/",
  "counterpart": null,
  "reason": "untracked"
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/debug.log'
api: /api/counterpart?page=/view/debug.log
status: 200
{
  "page": "/view/debug.log",
  "counterpart": null,
  "reason": "ignored"
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/build/'
api: /api/counterpart?page=/view/build/
status: 200
{
  "page": "/view/build/",
  "counterpart": null,
  "reason": "ignored"
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/view/build/out.bin'
api: /api/counterpart?page=/view/build/out.bin
status: 200
{
  "page": "/view/build/out.bin",
  "counterpart": null,
  "reason": "ignored"
}
? 0
```

## Test: a path neither the commit nor the working tree has is missing

```console
$ metab checkout --api '/api/counterpart?page=/view/gone.md'
api: /api/counterpart?page=/view/gone.md
status: 200
{
  "page": "/view/gone.md",
  "counterpart": null,
  "reason": "missing"
}
? 0
```

## Test: a served folder inside the repository maps under its place there

`checkout/docs` is served as its own root, so its root is the commit’s `docs` tree, and
the working tree is asked about a path below the served root.

```console
$ metab checkout/docs --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout/docs --api '/api/counterpart?page=/view/guide.md'
api: /api/counterpart?page=/view/guide.md
status: 200
{
  "page": "/view/guide.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs/guide.md"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout/docs --api '/api/counterpart?page=/view/staged.md'
api: /api/counterpart?page=/view/staged.md
status: 200
{
  "page": "/view/staged.md",
  "counterpart": null,
  "reason": "uncommitted"
}
? 0
```

## Test: a HEAD origin lacks maps at its merge base with its upstream branch

`ahead`’s HEAD is a commit no `refs/remotes/origin/*` reaches, so its working tree maps
at the merge base with its upstream branch, the commit origin has.
The root opens the repository.
An unchanged file and an edited file use their upstream branch, and a file only the
unpushed commit added has no counterpart.
Its pull-request pages map as they always do, since they do not depend on a commit.

```console
$ metab ahead --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo"
  },
  "reason": null
}
? 0
```

```console
$ metab ahead --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/main/README.md"
  },
  "reason": null
}
? 0
```

```console
$ metab ahead --api '/api/counterpart?page=/view/docs/guide.md'
api: /api/counterpart?page=/view/docs/guide.md
status: 200
{
  "page": "/view/docs/guide.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/main/docs/guide.md"
  },
  "reason": null
}
? 0
```

```console
$ metab ahead --api '/api/counterpart?page=/view/AHEAD.md'
api: /api/counterpart?page=/view/AHEAD.md
status: 200
{
  "page": "/view/AHEAD.md",
  "counterpart": null,
  "reason": "not_on_origin"
}
? 0
```

```console
$ metab ahead --api '/api/counterpart?page=/pull/7'
api: /api/counterpart?page=/pull/7
status: 200
{
  "page": "/pull/7",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pull/7"
  },
  "reason": null
}
? 0
```

## Test: a named upstream supplies the branch link

The checkout’s local branch has a different name.
The root and file use its published branch, including the slash in that branch’s name.

```console
$ metab branch --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/feature/docs"
  },
  "reason": null
}
? 0
```

```console
$ metab branch --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/feature/docs/README.md"
  },
  "reason": null
}
? 0
```

GitHub’s explicit branch namespace distinguishes a same-named tag.

```console
$ git -C branch tag feature/docs HEAD
? 0
```

```console
$ metab branch --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/refs/heads/feature/docs"
  },
  "reason": null
}
? 0
```

## Test: a branch with no upstream maps at its merge base with origin’s default branch

`topic` has no upstream, so its working tree maps at its merge base with `origin/HEAD`.
`alone` has neither, so no commit origin has is known for it.

```console
$ metab topic --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/README.md"
  },
  "reason": null
}
? 0
```

```console
$ metab topic --api '/api/counterpart?page=/view/TOPIC.md'
api: /api/counterpart?page=/view/TOPIC.md
status: 200
{
  "page": "/view/TOPIC.md",
  "counterpart": null,
  "reason": "not_on_origin"
}
? 0
```

```console
$ metab alone --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": null,
  "reason": "not_on_origin"
}
? 0
```

## Test: a pull request’s pages map to its tabs, and the list to the list

A changed file is GitHub’s anchor in the Changes tab: `diff-` and the SHA-256 of its
path.

```console
$ metab checkout --api '/api/counterpart?page=/pull/7'
api: /api/counterpart?page=/pull/7
status: 200
{
  "page": "/pull/7",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pull/7"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/pull/7/files'
api: /api/counterpart?page=/pull/7/files
status: 200
{
  "page": "/pull/7/files",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pull/7/files"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/pull/7/checks'
api: /api/counterpart?page=/pull/7/checks
status: 200
{
  "page": "/pull/7/checks",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pull/7/checks"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/pull/7/files/docs/guide.md'
api: /api/counterpart?page=/pull/7/files/docs/guide.md
status: 200
{
  "page": "/pull/7/files/docs/guide.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pull/7/files#diff-07fdd026b11c494c3b62c97f764f6939803c453389ebefd6b05e6f187d44859a"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/pulls'
api: /api/counterpart?page=/pulls
status: 200
{
  "page": "/pulls",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pulls"
  },
  "reason": null
}
? 0
```

## Test: a commit’s page maps when origin has the commit

A file in a commit’s page is the same anchor on the commit’s page.
`local-work`’s commit is on no origin ref, and a commit named by anything but its full
ID is no page: the commit page refuses it.

```console
$ metab checkout --api '/api/counterpart?page=/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348'
api: /api/counterpart?page=/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348
status: 200
{
  "page": "/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs/guide.md'
api: /api/counterpart?page=/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs/guide.md
status: 200
{
  "page": "/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/docs/guide.md",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/commit/6df6ba6b3b36f70b432b10b50b9a156ba27bc348#diff-07fdd026b11c494c3b62c97f764f6939803c453389ebefd6b05e6f187d44859a"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/commit/07546660123c7a9cc68d94bfb95ba5947c7f510a'
api: /api/counterpart?page=/commit/07546660123c7a9cc68d94bfb95ba5947c7f510a
status: 200
{
  "page": "/commit/07546660123c7a9cc68d94bfb95ba5947c7f510a",
  "counterpart": null,
  "reason": "not_on_origin"
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/commit/main'
api: /api/counterpart?page=/commit/main
status: 200
{
  "page": "/commit/main",
  "counterpart": null,
  "reason": "not_a_page"
}
? 0
```

## Test: an address that is no page has no counterpart

```console
$ metab checkout --api '/api/counterpart?page=/settings'
api: /api/counterpart?page=/settings
status: 200
{
  "page": "/settings",
  "counterpart": null,
  "reason": "not_a_page"
}
? 0
```

```console
$ metab checkout --api '/api/counterpart?page=/pull/0'
api: /api/counterpart?page=/pull/0
status: 200
{
  "page": "/pull/0",
  "counterpart": null,
  "reason": "not_a_page"
}
? 0
```

## Test: a folder with no repository on github.com has no counterpart

```console
$ metab plain --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": null,
  "reason": "no_repository"
}
? 0
```

```console
$ metab elsewhere --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": null,
  "reason": "no_repository"
}
? 0
```

## Test: a mirror’s default branch names its files and folders

A pin’s address names a path by its `GitPath` wire: `g1-ZG9jcw` is `docs`,
`g1-Z3VpZGUubWQ` is `guide.md`, and `g1-bm9uZQ` is `none`, which the commit lacks.
A folder’s spelling of a path is no page of a pin.
A mirror holds only its origin’s commits, so a pin is never asked about origin, and a
commit’s page maps when any of the mirror’s refs reaches it.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/counterpart?page=/view/g1-ZG9jcw/g1-Z3VpZGUubWQ'
api: /api/counterpart?page=/view/g1-ZG9jcw/g1-Z3VpZGUubWQ
status: 200
{
  "page": "/view/g1-ZG9jcw/g1-Z3VpZGUubWQ",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/topic/docs/guide.md"
  },
  "reason": null
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/counterpart?page=/view/g1-ZG9jcw/'
api: /api/counterpart?page=/view/g1-ZG9jcw/
status: 200
{
  "page": "/view/g1-ZG9jcw/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/topic/docs"
  },
  "reason": null
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/counterpart?page=/view/g1-bm9uZQ'
api: /api/counterpart?page=/view/g1-bm9uZQ
status: 200
{
  "page": "/view/g1-bm9uZQ",
  "counterpart": null,
  "reason": "missing"
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/counterpart?page=/view/README.md'
api: /api/counterpart?page=/view/README.md
status: 200
{
  "page": "/view/README.md",
  "counterpart": null,
  "reason": "not_a_page"
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/counterpart?page=/commit/c691256511d05858850bc7684ae062fea0d41132'
api: /api/counterpart?page=/commit/c691256511d05858850bc7684ae062fea0d41132
status: 200
{
  "page": "/commit/c691256511d05858850bc7684ae062fea0d41132",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/commit/c691256511d05858850bc7684ae062fea0d41132"
  },
  "reason": null
}
? 0
```

## Test: the mirrored root uses a repository or branch link

The mirror knows `topic` is the default and `wip` is another branch.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo"
  },
  "reason": null
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/tree/wip --api '/api/counterpart?page=/view/'
selection: tree
pin: 7a7d6596e515735d244dc1d942463c95851e139c (branch wip)
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/tree/wip"
  },
  "reason": null
}
? 0
```

## Test: a pull request’s detached head opens the repository at its root

Pull request 7’s head is on a fork, which only `refs/pull/7/head` reaches.
The Files root has no named branch on origin.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/counterpart?page=/view/'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo"
  },
  "reason": null
}
? 0
```

## Test: a checkout’s revision keeps a clean root and maps files origin has

A checkout served on a revision names paths as a pin does, and its working tree’s
changes are not what the page shows.
`local-work` is a commit no origin ref reaches.
Its root still opens the repository.

```console
$ metab checkout --ref main --api '/api/counterpart?page=/view/g1-UkVBRE1FLm1k'
api: /api/counterpart?page=/view/g1-UkVBRE1FLm1k
status: 200
{
  "page": "/view/g1-UkVBRE1FLm1k",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/blob/6df6ba6b3b36f70b432b10b50b9a156ba27bc348/README.md"
  },
  "reason": null
}
? 0
```

```console
$ metab checkout --ref local-work --api '/api/counterpart?page=/view/'
api: /api/counterpart?page=/view/
status: 200
{
  "page": "/view/",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo"
  },
  "reason": null
}
? 0
```

## Test: a request without a page is refused

```console
$ metab checkout --api /api/counterpart
api: /api/counterpart
status: 400
{
  "error": "\"page\" is a page's address, at most 16384 characters",
  "code": "invalid_request"
}
Error: /api/counterpart returned HTTP 400
? 1
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
