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
  mkdir url co tmp &&
  (cd url && METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --guided
  > fixture.log 2>&1) &&
  (cd co && METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --checkout
  > fixture.log 2>&1)
---
# Golden Tests: The Agent Skill’s Pull-Request Recipes

The recipes in `skills/metabrowser/SKILL.md` under “Read a Pull Request” and “Write a
Guided Review”, run as an agent runs them.
Each recipe writes `metab`’s answer to a file and reads the file with `jq` only when
`metab` succeeded, so its parts are consecutive blocks here, split where the recipe
chains with `&&`: each block then records the status of the command that ran last, and a
failure stops the recipe with a nonzero status.
`tests/test_skill_commands.py` fails when a recipe there is not a run of consecutive
blocks here joined with `&&`, with `<invocation>` read as `metab` and the fixture’s
cache and configuration directories, `<url>` as `https://github.com/octo/demo/pull/7`,
`<n>` as `7`, `<k>` as `1`, `<path>` as `src/app.txt`, and `<tmp>` as `tmp`.

`tests/github_pull_fixture.py` builds two homes before these commands run.
`url/home` holds a mirror of `https://github.com/octo/demo` and the records of pull
requests 7 to 10, each fetched once through `metab <pr-url> --no-serve` with a fake `gh`
and a fixed clock, with a guided review in the descriptions of 7 and 8 and two blocks in
9’s; `co/home` holds what a checkout’s folder server wrote for `co/checkout`: the
records of 7 and 10, with no store.
`gh` is `tests/fixtures/github-pull/no-gh/gh`, which fails every command, so nothing
here reaches GitHub.
A record fetched more than a minute ago reads as `stale`, which every one here is.

The recipe that refreshes a pull request beside a checkout is not run here: its
`"comparison": true` acquires a store from the checkout’s origin, which is GitHub.
`tests/test_cli_github_checkout_golden.py` posts the recipe’s own body in process with
the origin substituted, and checks that every field the recipe’s filter reads is in the
answer it pins.

## Test: the record says whether the pull request was read

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull?number=7' --format json > tmp/pull.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -r '.state, .reason, .last_refresh.outcome' tmp/pull.json
stale
null
succeeded
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

The recipe reads the route from the record the check wrote.

```console
$ ROUTE=$(jq -er .comparison_route tmp/pull.json) &&
> METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api "$ROUTE" --format json > tmp/diff.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -r '.manifest.files[] | "\(.id) \(.kind) \(.new.path // .old.path) +\(.additions) -\(.deletions)"' tmp/diff.json
f1 added docs/new.md +1 -0
f2 modified src/app.txt +1 -0
? 0
```

The same answer holds each file’s hunks, by the file’s `id`.

```console
$ jq -c '.patches["f2"].hunks[] | [.old_start, .new_start, [.lines[] | .op]]' tmp/diff.json
[1,1,["context","add"]]
? 0
```

## Test: a file at the head, read with Git in the mirror

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api /api/source/status --format json > tmp/status.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ LOC=$(jq -er --arg home "$HOME" '.location | sub("^~"; $home)' tmp/status.json) &&
> PIN=$(jq -er 'select(.ref == "refs/pull/7/head") | .pin' tmp/status.json) &&
> git -C "$LOC" show "$PIN:src/app.txt"
one
two
? 0
```

## Test: a pull request that cannot be read stops the recipes

Nothing is cached for 14, so the command asks the failing `gh`, serves the default
branch, and still exits 0; the record says why.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/14 --api '/api/plugin/github/pull?number=14' --format json > tmp/pull.json
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 14 (not opened: pull request 14 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
? 0
```

```console
$ jq -r '.state, .reason, .last_refresh.outcome, .pin_ref' tmp/pull.json
absent
not_cached
gh_failed
refs/remotes/origin/topic
? 0
```

The record has no comparison route, so the diff recipe stops before it runs `metab`.

```console
$ ROUTE=$(jq -er .comparison_route tmp/pull.json) &&
> METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/14 --api "$ROUTE" --format json > tmp/diff.json
? 1
```

The pin is the default branch, not the pull request’s head, so the file recipe stops
before it runs Git.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/14 --api /api/source/status --format json > tmp/status.json
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 14 (not opened: pull request 14 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
? 0
```

```console
$ LOC=$(jq -er --arg home "$HOME" '.location | sub("^~"; $home)' tmp/status.json) &&
> PIN=$(jq -er 'select(.ref == "refs/pull/14/head") | .pin' tmp/status.json) &&
> git -C "$LOC" show "$PIN:src/app.txt"
? 4
```

## Test: beside a checkout, a read fetches nothing

The checkout’s server has never fetched 8, and a read does not start a fetch, so the
record is absent with no refresh behind it.

```console
$ METABROWSER_CONFIG_DIR=$PWD/co/config METABROWSER_CACHE_DIR=$PWD/co/home metab co/checkout --api '/api/plugin/github/pull?number=8' --format json > tmp/pull.json
? 0
```

```console
$ jq -r '.state, .reason, .last_refresh.outcome' tmp/pull.json
absent
not_cached
null
? 0
```

10 has a record but no store, so its conversation stands while its diff does not.

```console
$ METABROWSER_CONFIG_DIR=$PWD/co/config METABROWSER_CACHE_DIR=$PWD/co/home metab co/checkout --api '/api/plugin/github/pull?number=10' --format json > tmp/pull.json
? 0
```

```console
$ jq -r '.state, .comparison_route, .record.unavailable.comparison' tmp/pull.json
stale
null
no_store
? 0
```

## Test: a guided review, read step by step

The guide of 7 is pinned to its head and merge base, so it answers `ready`; the first
answer gives the count of steps to read.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=1' --format json > tmp/step.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -r '.state, (.message // empty), .step_count, (.references[]? | [.kind, .pull, .path, .commit, .state] | map(select(. != null) | tostring) | join(" "))' tmp/step.json
ready
2
file src/app.txt ready
? 0
```

A step whose references are not all ready still answers `ready`; each reference says why
it is not.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=2' --format json > tmp/step.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -r '.state, (.message // empty), .step_count, (.references[]? | [.kind, .pull, .path, .commit, .state] | map(select(. != null) | tostring) | join(" "))' tmp/step.json
ready
2
file docs/new.md ready
file src/app.txt ready
file missing.txt path_not_changed
file src/app.txt range_unavailable
? 0
```

The description of 9 holds two blocks, so the page refuses the guide and says why.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/9 --api '/api/plugin/github/guided-review?number=9&step=1' --format json > tmp/step.json
selection: pull_request
pin: 0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd (pull request 9 head)
pull_request: 9 (closed; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -r '.state, (.message // empty), .step_count, (.references[]? | [.kind, .pull, .path, .commit, .state] | map(select(. != null) | tostring) | join(" "))' tmp/step.json
invalid
Use one guided-review block in the pull request description.
null
? 0
```

## Test: a pushed pull request names the steps to recheck

The guide of 7 matches its pull request, so nothing needs rechecking.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7' --format json > tmp/guide.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.state, .stale.changed_steps, .stale.changed_paths' tmp/guide.json
"ready"
null
null
? 0
```

8 carries the same guide, pinned to 7’s head, and a commit since changed files both of
its steps cite.

```console
$ METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab https://github.com/octo/demo/pull/8 --api '/api/plugin/github/guided-review?number=8' --format json > tmp/guide.json
selection: pull_request
pin: 8ae27617c9c475851b67ee69433d008836d112ba (pull request 8 head)
pull_request: 8 (merged; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.state, .stale.changed_steps, .stale.changed_paths' tmp/guide.json
"stale"
[1,2]
["docs/new.md","src/app.txt"]
? 0
```
