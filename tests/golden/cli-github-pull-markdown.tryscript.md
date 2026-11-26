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
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" .
  > fixture.log 2>&1
---
# Golden tests: a pull request’s text, rendered from the cache

`tests/github_pull_fixture.py` builds `home` before these commands run, as for
`cli-github-pull.tryscript.md`: a mirror of `https://github.com/octo/demo` and the
records of pull requests 7 to 10, each fetched once with a fake `gh` and a fixed clock.
Every command below answers from that cache, and `gh` is
`tests/fixtures/github-pull/no-gh/gh`, which fails every command.

## Test: the page’s text is Markdown rendered from the cached record

`pull-markdown` renders one text of the record through KPress in its sanitized mode: the
description (`body`), or one comment, review, or review comment by ID. The answer is the
record’s fetch time, the part, its rendered HTML, and the manifest of KPress’s
stylesheets, the same for every text.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull-markdown?number=7&part=body'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull-markdown?number=7&part=body
status: 200
{
  "number": 7,
  "fetched_at": "2026-09-17T12:00:00Z",
  "record_revision": "07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b",
  "part": "body",
  "html": "\n<div><div><p>The app counts to one.</p>\n<p>This teaches it <strong>two</strong>.</p></div></div>",
  "assets": {
...
  }
}
? 0
```

A part the record does not hold, or one that is not a part’s name, is refused.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull-markdown?number=7&part=review/1'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull-markdown?number=7&part=review/1
status: 404
{
  "error": "the record has no such part",
  "code": "unknown_part"
}
Error: /api/plugin/github/pull-markdown?number=7&part=review/1 returned HTTP 404
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull-markdown?number=7&part=../body'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/pull-markdown?number=7&part=../body
status: 400
{
  "error": "name a part of the pull request",
  "code": "invalid_part"
}
Error: /api/plugin/github/pull-markdown?number=7&part=../body returned HTTP 400
? 1
```

With no record cached there is nothing to render, and the answer says so.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/14 --api '/api/plugin/github/pull-markdown?number=14&part=body'
selection: pull_request
pin: c691256511d05858850bc7684ae062fea0d41132 (default branch topic)
pull_request: 14 (not opened: pull request 14 of https://github.com/octo/demo: gh exited 1 without an HTTP response (gh_failed); the pin is the default branch)
api: /api/plugin/github/pull-markdown?number=14&part=body
status: 404
{
  "error": "This pull request has not been loaded.",
  "code": "not_cached"
}
Error: /api/plugin/github/pull-markdown?number=14&part=body returned HTTP 404
? 1
```
