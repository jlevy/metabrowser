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
  METABROWSER_CONFIG_DIR="$PWD/config"
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py"
  . --guided > fixture.log 2>&1 || (cat fixture.log >&2 && exit 1)
---
# Guided PR reads the cached description and comparison

The first two steps keep the author’s order and read the actual patches from the fixture
mirror. The second demonstrates file-only, missing-path, and unresolved-line references.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-pr?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-pr?number=7
status: 200
{
  "record_revision": "eecb696cd6a2d4032d6da4feeb8ffaaf7847044f30d5d0d85ac9e98a6194ec60",
  "state": "ready",
  "summary": "Teach the app to count to two.",
  "overview": "The app's count and its explanation live in separate files.",
  "comparison": {
    "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
    "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
  },
  "step_count": 2,
  "step": 1,
  "title": "Start with the count",
  "note": "Check that the original value is preserved.",
  "references": [
    {
      "path": "src/app.txt",
      "side": "new",
      "start_line": 1,
      "end_line": 2,
      "state": "ready",
      "href": "/pull/7/files/src/app.txt",
      "rows": [
        {
          "old": 1,
          "new": 1,
          "op": "context",
          "text": "one"
        },
        {
          "old": null,
          "new": 2,
          "op": "add",
          "text": "two"
        }
      ]
    }
  ]
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-pr?number=7&step=2'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-pr?number=7&step=2
status: 200
{
  "record_revision": "eecb696cd6a2d4032d6da4feeb8ffaaf7847044f30d5d0d85ac9e98a6194ec60",
  "state": "ready",
  "summary": "Teach the app to count to two.",
  "overview": "The app's count and its explanation live in separate files.",
  "comparison": {
    "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
    "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
  },
  "step_count": 2,
  "step": 2,
  "title": "Read the new guide",
  "note": "Check the new docs against the behavior.",
  "references": [
    {
      "path": "docs/new.md",
      "side": "new",
      "start_line": 1,
      "end_line": 1,
      "state": "ready",
      "href": "/pull/7/files/docs/new.md",
      "rows": [
        {
          "old": null,
          "new": 1,
          "op": "add",
          "text": "# New"
        }
      ]
    },
    {
      "path": "src/app.txt",
      "side": null,
      "start_line": null,
      "end_line": null,
      "state": "file",
      "href": "/pull/7/files/src/app.txt",
      "rows": []
    },
    {
      "path": "missing.txt",
      "side": null,
      "start_line": null,
      "end_line": null,
      "state": "path_not_changed",
      "href": null,
      "rows": []
    },
    {
      "path": "src/app.txt",
      "side": "old",
      "start_line": 2,
      "end_line": 4,
      "state": "range_unavailable",
      "href": "/pull/7/files/src/app.txt",
      "rows": []
    }
  ]
}
? 0
```

The cached PR description may have a guide for a different comparison, an invalid guide,
or no guide. All three reads deliberately return without excerpts.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/8 --api '/api/plugin/github/guided-pr?number=8'
selection: pull_request
pin: 8ae27617c9c475851b67ee69433d008836d112ba (pull request 8 head)
pull_request: 8 (merged; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-pr?number=8
status: 200
{
  "record_revision": "0dd0882d8f17ed3b7129d5f890f5b7aa03f44d2fa24af1f92a5b7c79cd6bebb7",
  "state": "stale"
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/9 --api '/api/plugin/github/guided-pr?number=9'
selection: pull_request
pin: 0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd (pull request 9 head)
pull_request: 9 (closed; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-pr?number=9
status: 200
{
  "record_revision": "07fc5ffa0d4da8a0c6611f8997f7837dbb7e6f7af2f7b79cc42abc0f8b5e3a9e",
  "state": "invalid",
  "message": "Use one guided-pr block in the pull request description."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/10 --api '/api/plugin/github/guided-pr?number=10'
selection: pull_request
pin: 7a7d6596e515735d244dc1d942463c95851e139c (pull request 10 head)
pull_request: 10 (draft; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-pr?number=10
status: 200
{
  "record_revision": "b61b65443f1b94641b404dc8f04f65cdc54e53ccda7d5bdb50f0628bc0737ff4",
  "state": "absent"
}
? 0
```

The guide’s local address opens the pull request description on GitHub.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/counterpart?page=/pull/7/guided'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/counterpart?page=/pull/7/guided
status: 200
{
  "page": "/pull/7/guided",
  "counterpart": {
    "provider": "github",
    "label": "View on GitHub",
    "url": "https://github.com/octo/demo/pull/7"
  },
  "reason": null
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
