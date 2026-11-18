---
sandbox: true
path:
  - ../fixtures/github-pull/no-gh
  - ../../.venv/bin
requires:
  - metab
  - jq
  - git
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
patterns:
  ROOT_ARG: '\[ROOT\]'
before: >-
  mkdir url co &&
  (cd url && METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" .
  > fixture.log 2>&1) &&
  (cd co && METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --checkout
  > fixture.log 2>&1)
---
# Golden Tests: The Agent Skill’s Pull-Request Recipes

The recipes in `skills/metabrowser/SKILL.md` under “Read a Pull Request”, run as an
agent runs them: each `--api` answer piped to `jq`. `tests/test_skill_commands.py` fails
when a recipe there and its command here differ, with `<invocation>` read as `metab` and
the fixture’s cache and configuration directories, `<url>` as
`https://github.com/octo/demo/pull/7`, `<n>` as `7`, and `<path>` as `src/app.txt`.

`tests/github_pull_fixture.py` builds two homes before these commands run.
`url/home` holds a mirror of `https://github.com/octo/demo` and the records of pull
requests 7 to 10, each fetched once through `metab <pr-url> --no-serve` with a fake `gh`
and a fixed clock; `co/home` holds what a checkout’s folder server wrote for
`co/checkout`: the records of 7 and 10, with no store.
`gh` is `tests/fixtures/github-pull/no-gh/gh`, which fails every command, so nothing
here reaches GitHub.
A record fetched more than a minute ago reads as `stale`, which every one here is.

The recipe that refreshes a pull request beside a checkout is not run here: its
`"comparison": true` acquires a store from the checkout’s origin, which is GitHub.
`tests/test_cli_github_checkout_golden.py` runs that request in process with the origin
substituted, and pins the comparison it attaches.

## Test: the record says whether the pull request was read

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull?number=7' --format json |
>   jq -r '.state, .reason, .last_refresh.outcome'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
stale
null
succeeded
? 0
```

Nothing is cached for 14, so the command asks the failing `gh`, serves the default
branch, and still exits 0; the record says why.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/14 --api '/api/plugin/github/pull?number=14' --format json |
>   jq -r '.state, .reason, .last_refresh.outcome, .pin_ref'
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 14 (not opened: pull request 14 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
absent
not_cached
gh_failed
refs/remotes/origin/topic
? 0
```

`--no-serve` prints lines for a person and takes no `--format`.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --no-serve --format json 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --format not valid with --no-serve                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: the diff is the record’s comparison route

```console
$ ROUTE=$(METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull?number=7' --format json |
>   jq -r .comparison_route) &&
> METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api "$ROUTE" --format json |
>   jq -r '.manifest.files[] | "\(.kind) \(.new.path // .old.path) +\(.additions) -\(.deletions)"'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
added docs/new.md +1 -0
modified src/app.txt +1 -0
? 0
```

## Test: a file at the head, read with Git in the mirror

```console
$ LOC=$(METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api /api/source/status --format json | jq -r .location | sed "s|^~|$HOME|") &&
> PIN=$(METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api /api/source/status --format json | jq -r .pin) &&
> git -C "$LOC" show "$PIN:src/app.txt"
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
one
two
? 0
```

## Test: beside a checkout, a read fetches nothing

The checkout’s server has never fetched 8, and a read does not start a fetch, so the
record is absent with no refresh behind it.

```console
$ METABROWSER_CONFIG_DIR=$PWD/co/config METABROWSER_CACHE_DIR=$PWD/co/home metab co/checkout --api '/api/plugin/github/pull?number=8' --format json |
>   jq -r '.state, .reason, .last_refresh.outcome'
absent
not_cached
null
? 0
```

10 has a record but no store, so its conversation stands while its diff does not.

```console
$ METABROWSER_CONFIG_DIR=$PWD/co/config METABROWSER_CACHE_DIR=$PWD/co/home metab co/checkout --api '/api/plugin/github/pull?number=10' --format json |
>   jq -r '.state, .comparison_route, .record.unavailable.comparison'
stale
null
no_store
? 0
```
