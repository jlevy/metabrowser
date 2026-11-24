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
# Guided Review reads the cached description and comparison

The first two steps keep the author’s order and read the actual patches from the fixture
mirror. The second demonstrates a reference with no range, which shows its file’s whole
patch, and missing-path and unresolved-line references.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "5b3e8db1e0012e725ad0118cfe608208412c91db24ee5af40cbe2c93f2642060",
  "state": "ready",
  "comparison": {
    "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
    "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
  },
  "step_count": 2,
  "titles": [
    "Start with the count",
    "Read the new guide"
  ],
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
      "hunks": [
        {
          "old_start": 1,
          "old_count": 1,
          "new_start": 1,
          "new_count": 2,
          "heading": null,
          "lines": [
            {
              "op": "context",
              "text": "one",
              "text_b64": null,
              "no_newline": false
            },
            {
              "op": "add",
              "text": "two",
              "text_b64": null,
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    }
  ],
  "assets": {
    "schema_version": "kpress-asset-manifest-v2",
    "assets": [
      {
        "id": "css/style-tokens.css",
        "kind": "package",
        "path": "css/style-tokens.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8efb2fa07a0a0370",
        "output_path": "css/style-tokens.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/style-tokens.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/syntax.css",
        "kind": "package",
        "path": "css/syntax.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "807cf5be35b5a8dd",
        "output_path": "css/syntax.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/syntax.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/document.css",
        "kind": "package",
        "path": "css/document.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "bc14c4d38a7a4d65",
        "output_path": "css/document.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/document.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/components.css",
        "kind": "package",
        "path": "css/components.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "7c60e6bb7d672589",
        "output_path": "css/components.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/components.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print.css",
        "kind": "package",
        "path": "css/print.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8a8f7b928ad6be2f",
        "output_path": "css/print.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/print.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print-fonts.css",
        "kind": "package",
        "path": "css/print-fonts.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "f4a0751b8416f372",
        "output_path": "css/print-fonts.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/print-fonts.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-400-normal.css",
        "kind": "package",
        "path": "css/mono-planetaire-400-normal.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "9a5f82ca54019902",
        "output_path": "css/mono-planetaire-400-normal.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-400-normal.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-700-normal.css",
        "kind": "package",
        "path": "css/mono-planetaire-700-normal.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "c5232ad5d38dc5a6",
        "output_path": "css/mono-planetaire-700-normal.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-700-normal.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-400-italic.css",
        "kind": "package",
        "path": "css/mono-planetaire-400-italic.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "34bd1d5b7aa5a794",
        "output_path": "css/mono-planetaire-400-italic.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-400-italic.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-700-italic.css",
        "kind": "package",
        "path": "css/mono-planetaire-700-italic.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8fe04148a6caac2d",
        "output_path": "css/mono-planetaire-700-italic.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-700-italic.css",
        "entry_point": true,
        "loading": "stylesheet"
      }
    ]
  }
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=2'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7&step=2
status: 200
{
  "record_revision": "5b3e8db1e0012e725ad0118cfe608208412c91db24ee5af40cbe2c93f2642060",
  "state": "ready",
  "comparison": {
    "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
    "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
  },
  "step_count": 2,
  "titles": [
    "Start with the count",
    "Read the new guide"
  ],
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
      "hunks": [
        {
          "old_start": 0,
          "old_count": 0,
          "new_start": 1,
          "new_count": 1,
          "heading": null,
          "lines": [
            {
              "op": "add",
              "text": "# New",
              "text_b64": null,
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    {
      "path": "src/app.txt",
      "side": null,
      "start_line": null,
      "end_line": null,
      "state": "ready",
      "href": "/pull/7/files/src/app.txt",
      "hunks": [
        {
          "old_start": 1,
          "old_count": 1,
          "new_start": 1,
          "new_count": 2,
          "heading": null,
          "lines": [
            {
              "op": "context",
              "text": "one",
              "text_b64": null,
              "no_newline": false
            },
            {
              "op": "add",
              "text": "two",
              "text_b64": null,
              "no_newline": false
            }
          ]
        }
      ],
      "truncated": false
    },
    {
      "path": "missing.txt",
      "side": null,
      "start_line": null,
      "end_line": null,
      "state": "path_not_changed",
      "href": null,
      "hunks": [],
      "truncated": false
    },
    {
      "path": "src/app.txt",
      "side": "old",
      "start_line": 2,
      "end_line": 4,
      "state": "range_unavailable",
      "href": "/pull/7/files/src/app.txt",
      "hunks": [],
      "truncated": false
    }
  ],
  "assets": {
    "schema_version": "kpress-asset-manifest-v2",
    "assets": [
      {
        "id": "css/style-tokens.css",
        "kind": "package",
        "path": "css/style-tokens.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8efb2fa07a0a0370",
        "output_path": "css/style-tokens.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/style-tokens.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/syntax.css",
        "kind": "package",
        "path": "css/syntax.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "807cf5be35b5a8dd",
        "output_path": "css/syntax.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/syntax.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/document.css",
        "kind": "package",
        "path": "css/document.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "bc14c4d38a7a4d65",
        "output_path": "css/document.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/document.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/components.css",
        "kind": "package",
        "path": "css/components.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "7c60e6bb7d672589",
        "output_path": "css/components.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/components.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print.css",
        "kind": "package",
        "path": "css/print.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8a8f7b928ad6be2f",
        "output_path": "css/print.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/print.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print-fonts.css",
        "kind": "package",
        "path": "css/print-fonts.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "f4a0751b8416f372",
        "output_path": "css/print-fonts.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/print-fonts.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-400-normal.css",
        "kind": "package",
        "path": "css/mono-planetaire-400-normal.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "9a5f82ca54019902",
        "output_path": "css/mono-planetaire-400-normal.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-400-normal.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-700-normal.css",
        "kind": "package",
        "path": "css/mono-planetaire-700-normal.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "c5232ad5d38dc5a6",
        "output_path": "css/mono-planetaire-700-normal.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-700-normal.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-400-italic.css",
        "kind": "package",
        "path": "css/mono-planetaire-400-italic.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "34bd1d5b7aa5a794",
        "output_path": "css/mono-planetaire-400-italic.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-400-italic.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-700-italic.css",
        "kind": "package",
        "path": "css/mono-planetaire-700-italic.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8fe04148a6caac2d",
        "output_path": "css/mono-planetaire-700-italic.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-700-italic.css",
        "entry_point": true,
        "loading": "stylesheet"
      }
    ]
  }
}
? 0
```

The cached PR description may have a guide for a different comparison, an invalid guide,
or no guide. A guide for a different comparison is stale, and still answers its step,
read at the pull request’s current comparison, with what changed since for an agent that
brings the guide up to date: pull request 8’s branch was rebased past the guide’s head,
so its history is `rewritten`, both cited files changed, so both steps are marked, and
the file step 1 cites is no longer in the pull request’s changes.
An invalid guide and an absent one return without excerpts.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/8 --api '/api/plugin/github/guided-review?number=8'
selection: pull_request
pin: 8ae27617c9c475851b67ee69433d008836d112ba (pull request 8 head)
pull_request: 8 (merged; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=8
status: 200
{
  "record_revision": "68097bda4fea21c13b15976bab4fcc580a1667136df5ec513e270cb28b07eb0b",
  "state": "stale",
  "stale": {
    "guide": {
      "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "head": "85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"
    },
    "current": {
      "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
      "head": "8ae27617c9c475851b67ee69433d008836d112ba"
    },
    "github_newer": false,
    "history": "rewritten",
    "commit_count": 1,
    "commits": [
      {
        "sha": "8ae27617c9c475851b67ee69433d008836d112ba",
        "subject": "more guide"
      }
    ],
    "changed_paths": [
      "docs/new.md",
      "src/app.txt"
    ],
    "changed_steps": [
      1,
      2
    ]
  },
  "comparison": {
    "merge_base": "f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",
    "head": "8ae27617c9c475851b67ee69433d008836d112ba"
  },
  "step_count": 2,
  "titles": [
    "Start with the count",
    "Read the new guide"
  ],
  "step": 1,
  "title": "Start with the count",
  "note": "Check that the original value is preserved.",
  "references": [
    {
      "path": "src/app.txt",
      "side": "new",
      "start_line": 1,
      "end_line": 2,
      "state": "path_not_changed",
      "href": null,
      "hunks": [],
      "truncated": false
    }
  ],
  "assets": {
    "schema_version": "kpress-asset-manifest-v2",
    "assets": [
      {
        "id": "css/style-tokens.css",
        "kind": "package",
        "path": "css/style-tokens.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8efb2fa07a0a0370",
        "output_path": "css/style-tokens.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/style-tokens.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/syntax.css",
        "kind": "package",
        "path": "css/syntax.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "807cf5be35b5a8dd",
        "output_path": "css/syntax.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/syntax.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/document.css",
        "kind": "package",
        "path": "css/document.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "bc14c4d38a7a4d65",
        "output_path": "css/document.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/document.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/components.css",
        "kind": "package",
        "path": "css/components.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "7c60e6bb7d672589",
        "output_path": "css/components.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/components.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print.css",
        "kind": "package",
        "path": "css/print.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8a8f7b928ad6be2f",
        "output_path": "css/print.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/print.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/print-fonts.css",
        "kind": "package",
        "path": "css/print-fonts.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "f4a0751b8416f372",
        "output_path": "css/print-fonts.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/print-fonts.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-400-normal.css",
        "kind": "package",
        "path": "css/mono-planetaire-400-normal.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "9a5f82ca54019902",
        "output_path": "css/mono-planetaire-400-normal.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-400-normal.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-700-normal.css",
        "kind": "package",
        "path": "css/mono-planetaire-700-normal.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "c5232ad5d38dc5a6",
        "output_path": "css/mono-planetaire-700-normal.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-700-normal.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-400-italic.css",
        "kind": "package",
        "path": "css/mono-planetaire-400-italic.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "34bd1d5b7aa5a794",
        "output_path": "css/mono-planetaire-400-italic.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-400-italic.css",
        "entry_point": true,
        "loading": "stylesheet"
      },
      {
        "id": "css/mono-planetaire-700-italic.css",
        "kind": "package",
        "path": "css/mono-planetaire-700-italic.css",
        "mode": "hosted",
        "media_type": "text/css",
        "content_hash": "8fe04148a6caac2d",
        "output_path": "css/mono-planetaire-700-italic.css",
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.10/css/mono-planetaire-700-italic.css",
        "entry_point": true,
        "loading": "stylesheet"
      }
    ]
  }
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/9 --api '/api/plugin/github/guided-review?number=9'
selection: pull_request
pin: 0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd (pull request 9 head)
pull_request: 9 (closed; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=9
status: 200
{
  "record_revision": "2de61d7e403b24595ab0a6ca6e1ce70c621358175d1b6e255e32830e538cec00",
  "state": "invalid",
  "message": "Use one guided-review block in the pull request description."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/10 --api '/api/plugin/github/guided-review?number=10'
selection: pull_request
pin: 7a7d6596e515735d244dc1d942463c95851e139c (pull request 10 head)
pull_request: 10 (draft; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=10
status: 200
{
  "record_revision": "b61b65443f1b94641b404dc8f04f65cdc54e53ccda7d5bdb50f0628bc0737ff4",
  "state": "absent"
}
? 0
```

A step past the guide’s last, a step that is not a positive integer, and a pull request
with no cached record are each answered as that.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=3'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7&step=3
status: 200
{
  "record_revision": "5b3e8db1e0012e725ad0118cfe608208412c91db24ee5af40cbe2c93f2642060",
  "state": "step_not_found"
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=0'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7&step=0
status: 400
{
  "error": "step must be a positive integer",
  "code": "invalid_request"
}
Error: /api/plugin/github/guided-review?number=7&step=0 returned HTTP 400
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=11'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=11
status: 200
{
  "record_revision": null,
  "state": "not_cached"
}
? 0
```

The description introduces the guide: its Markdown, which Conversation and Guided Review
both render, leaves out the guided-review block.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/pull-markdown?number=7&part=body' > markdown.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ grep -c 'softschema\|guided-review' markdown.json
0
? 1
```

```console
$ grep -o 'The app learns to count to two.' markdown.json
The app learns to count to two.
? 0
```

The guide’s local address, and Conversation’s, open the pull request description on
GitHub.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/counterpart?page=/pull/7/conversation'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/counterpart?page=/pull/7/conversation
status: 200
{
  "page": "/pull/7/conversation",
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
