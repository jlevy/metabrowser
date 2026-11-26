---
sandbox: true
requires:
  - jq
path:
  - ../fixtures/github-pull/no-gh
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
patterns:
  BUILD: '[0-9a-f]{12}'
  STORE: '[0-9a-f]{16}'
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
The guide of 7 has no groups, so its `outline` lists its steps, and each step’s `group`
is null.

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
  "outline": [
    {
      "kind": "step",
      "step": 1,
      "title": "Start with the count"
    },
    {
      "kind": "step",
      "step": 2,
      "title": "Read the new guide"
    }
  ],
  "step": 1,
  "group": null,
  "title": "Start with the count",
  "note": "Check that the original value is preserved.",
  "note_html": "\n<div><div><p>Check that the original value is preserved.</p></div></div>",
  "note_refusal": null,
  "group_note_html": null,
  "group_note_refusal": null,
  "references": [
    {
      "kind": "file",
      "path": "src/app.txt",
      "side": "new",
      "start_line": 1,
      "end_line": 2,
      "pull": null,
      "commit": null,
      "state": "ready",
      "rendered": null,
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
      "truncated": false,
      "comparison": null,
      "target": null
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/style-tokens.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/syntax.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/document.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/components.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/print.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/print-fonts.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-400-normal.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-700-normal.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-400-italic.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-700-italic.css",
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
  "outline": [
    {
      "kind": "step",
      "step": 1,
      "title": "Start with the count"
    },
    {
      "kind": "step",
      "step": 2,
      "title": "Read the new guide"
    }
  ],
  "step": 2,
  "group": null,
  "title": "Read the new guide",
  "note": "Check the new docs against the behavior.",
  "note_html": "\n<div><div><p>Check the new docs against the behavior.</p></div></div>",
  "note_refusal": null,
  "group_note_html": null,
  "group_note_refusal": null,
  "references": [
    {
      "kind": "file",
      "path": "docs/new.md",
      "side": "new",
      "start_line": 1,
      "end_line": 1,
      "pull": null,
      "commit": null,
      "state": "ready",
      "rendered": null,
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
      "truncated": false,
      "comparison": null,
      "target": null
    },
    {
      "kind": "file",
      "path": "src/app.txt",
      "side": null,
      "start_line": null,
      "end_line": null,
      "pull": null,
      "commit": null,
      "state": "ready",
      "rendered": null,
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
      "truncated": false,
      "comparison": null,
      "target": null
    },
    {
      "kind": "file",
      "path": "missing.txt",
      "side": null,
      "start_line": null,
      "end_line": null,
      "pull": null,
      "commit": null,
      "state": "path_not_changed",
      "rendered": null,
      "href": null,
      "hunks": [],
      "truncated": false,
      "comparison": null,
      "target": null
    },
    {
      "kind": "file",
      "path": "src/app.txt",
      "side": "old",
      "start_line": 2,
      "end_line": 4,
      "pull": null,
      "commit": null,
      "state": "range_unavailable",
      "rendered": null,
      "href": "/pull/7/files/src/app.txt",
      "hunks": [],
      "truncated": false,
      "comparison": null,
      "target": null
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/style-tokens.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/syntax.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/document.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/components.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/print.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/print-fonts.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-400-normal.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-700-normal.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-400-italic.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-700-italic.css",
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
  "outline": [
    {
      "kind": "step",
      "step": 1,
      "title": "Start with the count"
    },
    {
      "kind": "step",
      "step": 2,
      "title": "Read the new guide"
    }
  ],
  "step": 1,
  "group": null,
  "title": "Start with the count",
  "note": "Check that the original value is preserved.",
  "note_html": "\n<div><div><p>Check that the original value is preserved.</p></div></div>",
  "note_refusal": null,
  "group_note_html": null,
  "group_note_refusal": null,
  "references": [
    {
      "kind": "file",
      "path": "src/app.txt",
      "side": "new",
      "start_line": 1,
      "end_line": 2,
      "pull": null,
      "commit": null,
      "state": "path_not_changed",
      "rendered": null,
      "href": null,
      "hunks": [],
      "truncated": false,
      "comparison": null,
      "target": null
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/style-tokens.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/syntax.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/document.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/components.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/print.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/print-fonts.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-400-normal.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-700-normal.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-400-italic.css",
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
        "public_url": "/kpress-static/@e619e63103603bcc/v0.3.11/css/mono-planetaire-700-italic.css",
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

# Groups

A guide may gather its steps in groups, one level deep, and mix them with steps outside
any group. Each answer with a step carries the guide’s `outline` in reading order: a
group with its title, its note or null, and its steps, and a step outside a group.
Steps are numbered through the groups, as `step`, `titles`, and `changed_steps` count
them, and a step’s `group` is the index in `outline` of the group it is in, or null.
An author who puts each step of 8’s guide in a group, the first with a note, and keeps
its pins writes a guide that is still stale, whose changed steps count through the
groups.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 8 grouped
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/8 --api '/api/plugin/github/guided-review?number=8&step=2' --format json > grouped.json
selection: pull_request
pin: 8ae27617c9c475851b67ee69433d008836d112ba (pull request 8 head)
pull_request: 8 (merged; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq '{state, changed_steps: .stale.changed_steps, step_count, titles, outline, step, group, title}' grouped.json
{
  "state": "stale",
  "changed_steps": [
    1,
    2
  ],
  "step_count": 2,
  "titles": [
    "Start with the count",
    "Read the new guide"
  ],
  "outline": [
    {
      "kind": "group",
      "title": "The count",
      "note": "Read the value before its explanation.",
      "children": [
        {
          "kind": "step",
          "step": 1,
          "title": "Start with the count"
        }
      ]
    },
    {
      "kind": "group",
      "title": "The docs",
      "note": null,
      "children": [
        {
          "kind": "step",
          "step": 2,
          "title": "Read the new guide"
        }
      ]
    }
  ],
  "step": 2,
  "group": 1,
  "title": "Read the new guide"
}
? 0
```

An author who moves 7’s first step into a group and leaves its second outside one writes
a mixed guide: the first step is in group 0, and the second in none.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 mixed
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=1' --format json > mixed.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.state, .outline, .group' mixed.json
"ready"
[{"kind":"group","title":"The count","note":"Read the value before its explanation.","children":[{"kind":"step","step":1,"title":"Start with the count"}]},{"kind":"step","step":2,"title":"Read the new guide"}]
0
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=2' --format json > mixed.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.state, .group, .title' mixed.json
"ready"
null
"Read the new guide"
? 0
```

A longer guide whose two groups each hold two steps numbers them 1 to 4 through the
groups, not by entry: the second group’s steps are 3 and 4, and step 3’s group is 1.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 longer
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=3' --format json > longer.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.state, .step_count, .outline, .step, .group, .title' longer.json
"ready"
4
[{"kind":"group","title":"The count","note":null,"children":[{"kind":"step","step":1,"title":"Start with the count"},{"kind":"step","step":2,"title":"Compare the old count"}]},{"kind":"group","title":"The docs","note":null,"children":[{"kind":"step","step":3,"title":"Read the new guide"},{"kind":"step","step":4,"title":"Read each file whole"}]}]
3
1
"Read the new guide"
? 0
```

A group without steps is refused, as a guide without steps is, and so is a group inside
a group: each says where, below `collection`.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 empty-group
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "3a845e764c4ec13e650bcd2f0aa2070b91bbf6d5622c7e90744d03c3085a687f",
  "state": "invalid",
  "message": "The guided-review block does not satisfy the v1 SoftSchema at items.0.items."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 nested-group
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "7a8064e614fdf0641ca368682429b46d86d7a9f4cffd57d7757e6aa89c7acf71",
  "state": "invalid",
  "message": "The guided-review block does not satisfy the v1 SoftSchema at items.0.items.0."
}
? 0
```

A guide whose steps and groups together pass `MAX_ITEMS` is refused in words that say
so, even when each of its lists is within its own bound, as here: two groups whose steps
pass it together.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 past-max-items
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "cdb594bebd68f182cd784b6b04e867d5a08cd44cfa280ac815fb67ae6941c1e1",
  "state": "invalid",
  "message": "This guide has more than 40 steps and groups."
}
? 0
```

# Notes

A note is Markdown, rendered as the description is: KPress in its sanitized mode, then
the inert allowlist against the pull request’s page, in the server’s Markdown child
under its deadline.
Each answer with a step carries its note as written, `note`, and that
render beside it, `note_html`, which is null when the render is refused; the page then
shows the note as typed.
The step that opens a group with a note carries the group’s note rendered so,
`group_note_html`, and the outline keeps it as written.
A title stays text.
In 7’s guide with Markdown in its notes, the first step’s two opening
lines join into one paragraph, as two lines do in a description, its list needs no blank
line before it, and its link is made absolute against the pull request’s page.
Its raw HTML is reduced to the allowlist: the `<b>` stays, the script is dropped, an
image from a relative source becomes a link to it, and an image over `https` keeps its
source and sends no referrer.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 markdown
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=1' --format json > notes.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -r '.state, .title, .note, .note_html, .outline[0].note, .group_note_html' notes.json
ready
Start with the <b>count</b>
Check that the **original** value
is preserved:
- `one` stays,
- and [the guide](docs/new.md) says so.

Raw <b>bold</b><script>alert(1)</script> <img src=x onerror=alert(1)> ![chart](https://example.com/chart.png)

<div><div><p>Check that the <strong>original</strong> value
is preserved:</p>
<ul>
<li><code>one</code> stays,</li>
<li>and <a href="https://github.com/octo/demo/pull/docs/new.md" target="_blank" rel="noopener noreferrer" data-metabrowser-path-relative="">the guide</a> says so.</li>
</ul>
<p>Raw <b>bold</b> <a href="https://github.com/octo/demo/pull/x" target="_blank" rel="noopener noreferrer"><span class="mb-image-fallback" data-tip-text="https://github.com/octo/demo/pull/x">image</span></a> <img loading="lazy" referrerpolicy="no-referrer" src="https://example.com/chart.png" alt="chart"></p></div></div>
Read the `count` before *its* explanation.

<div><div><p>Read the <code>count</code> before <em>its</em> explanation.</p></div></div>
? 0
```

The group’s second step is in the group but does not open it, so it carries no group’s
note.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=2' --format json > notes.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.group, .group_note_html, .note_html' notes.json
0
null
"\n<div><div><p>Check what the count replaced.</p></div></div>"
? 0
```

A note whose render is refused answers why beside its null `note_html`: `note_refusal`
is the code the pull-markdown route answers a text’s refusal with, and
`group_note_refusal` says the same of a group’s note.
The page shows the note as typed with the line a description’s refusal says, and keeps
no answer whose renderer was busy or could not start, so that step is read again
(`cli-ui-github-guided-review.tryscript.md`). In 7’s guide with a slow note, the first
step’s note is 100 unpaired `[` before 60 KiB of `%`, which KPress takes seconds to
render, so a deadline shortened to 250 ms through its environment variable refuses it on
any machine.
The server says on standard error which note it refused, and after how long;
the step reads as before, with its excerpt.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 slow-note
? 0
```

```console
$ METABROWSER_INERT_RENDER_DEADLINE_MS=250 METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=1' --format json > notes.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
[..] metabrowser.diff.markdown_projection_worker | Refused rendering 'pull-7-guided-review-note.md' (sha256:6d547e03b6bb237dc4ebdb452e24980c5a74749b35eef82755adf7ab51270c30) after [..] s: render_deadline
? 0
```

```console
$ jq -c '.state, .note_html, .note_refusal, (.note | length), .group_note_refusal, [.references[].state]' notes.json
"ready"
null
"render_deadline"
61540
null
["ready"]
? 0
```

# Documents

A file a step cites whole that the rendered route renders, by that route’s own rule on
both sides of the change, answers `rendered`, its format, and no hunks.
The page draws it whole from the comparison route’s one-file answer and the rendered
route, within their own bounds, so the guided route reads no patch for it and charges it
nothing against the step’s budget for whole files (`MAX_STEP_PATCH_BYTES`). In a
documents build, pull request 7 also adds `config/settings.yaml` and `docs/large.md`, a
Markdown file whose whole patch charges past that budget, and its guide ends on a step
that cites them whole: each answers `ready`, and `src/app.txt`, cited whole after them,
still has the whole budget for its patch.
Every other reference answers `rendered` null, as the steps above do.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" documents --guided-large-document > documents.log 2>&1 || (cat documents.log >&2 && exit 1)
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/documents/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=3' --format json > documents.json
selection: pull_request
pin: 12b02e42ead211903e888a8862ac6d47784204c5 (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

```console
$ jq -c '.state, .title, (.references[] | [.path, .side, .state, .rendered, (.hunks | length)])' documents.json
"ready"
"Read the new guide whole"
["docs/new.md",null,"ready","markdown",0]
["config/settings.yaml",null,"ready","yaml",0]
["docs/large.md",null,"ready","markdown",0]
["src/app.txt",null,"ready",null,1]
? 0
```

# References past the pull request

A step can cite three things besides a file of its own pull request: another pull
request, `{pull}`; a file another pull request changes, `{pull, path}`; and a commit,
`{commit}`. Each answer names its `kind` and carries every field, null where its kind
has none. Each is read from this copy alone, and none is ever stale.
In 7’s guide of every kind, the second step cites 8, which is merged, then 10’s draft
document and 9’s change to `src/app.txt`, then 50, which this copy knows from its list
of pull requests alone, and 2000, which it does not know at all.
Then it cites 7’s own head as a commit, and a commit the store lacks.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 kinds
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7&step=2' --format json > kinds.json
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
? 0
```

A `{pull}` answers the title, state, and stack place a row names, from the pull
request’s record or else its row in the list, or `not_cached` when this copy has
neither. Its address is the pull request’s page either way.
No stack is known here, so `stack` is null.
A `{commit}` answers its subject and when it was committed, and `commit_unavailable`
when the store lacks it.

```console
$ jq -c '.state, (.references[] | {kind, pull, commit, state, href, target})' kinds.json
"ready"
{"kind":"pull","pull":8,"commit":null,"state":"ready","href":"/pull/8","target":{"title":"Say more in the guide","state":"merged","stack":null,"author":"maintainer","avatar":null}}
{"kind":"pull_file","pull":10,"commit":null,"state":"ready","href":"/pull/10/files/docs/draft.md","target":null}
{"kind":"pull_file","pull":9,"commit":null,"state":"ready","href":"/pull/9/files/src/app.txt","target":null}
{"kind":"pull","pull":50,"commit":null,"state":"ready","href":"/pull/50","target":{"title":"Work item 50","state":"open","stack":null,"author":"contributor","avatar":null}}
{"kind":"pull","pull":2000,"commit":null,"state":"not_cached","href":"/pull/2000","target":null}
{"kind":"commit","pull":null,"commit":"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a","state":"ready","href":"/commit/85fcb2fa9e77eb5db485ffef445cbbc645d6db4a","target":{"subject":"count to two","committed_at":"2026-08-29T14:40:00Z"}}
{"kind":"commit","pull":null,"commit":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","state":"commit_unavailable","href":null,"target":null}
? 0
```

A `{pull, path}` is read at that pull request’s current comparison, as a `{path}` alone
is at the guide’s: a document whole, from that pull request’s own routes, which its
`comparison` names, and any other file as its whole patch.

```console
$ jq -c '.references[1:3][] | [.path, .rendered, (.hunks | length), .comparison.merge_base, .comparison.head]' kinds.json
["docs/draft.md","markdown",0,"c691256511d05858850bc7684ae062fea0d41132","7a7d6596e515735d244dc1d942463c95851e139c"]
["src/app.txt",null,1,"f92fd713acd521d4ebb62fb9f345ec927b8b6d1b","0fe10aeb84bee6fe05150d6d9f6da3f4d68549bd"]
? 0
```

```console
$ jq '.references[1].comparison' kinds.json
{
  "merge_base": "c691256511d05858850bc7684ae062fea0d41132",
  "head": "7a7d6596e515735d244dc1d942463c95851e139c",
  "route": "/api/plugin/github/pull-comparison?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&base_policy=merge_base&build=[BUILD]&store=[STORE]",
  "image_route": "/api/plugin/github/pull-image?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&store=[STORE]",
  "rendered_route": "/api/plugin/github/pull-rendered-diff?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&store=[STORE]"
}
? 0
```

A `{pull, path}` takes no range, and a commit is cited alone, by its full SHA. The
refusal names the field that goes wrong.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 pull-file-range
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "c45e40d11fbc230d39524aff52ffa37f378017259dde655aa23a909f91802bd3",
  "state": "invalid",
  "message": "The guided-review block does not satisfy the v1 SoftSchema at items.1.references.0.end_line."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 commit-and-path
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "0ce2d3510d198ed3b03078eca300f119df0ed8cc7f7f5af79bfbb5c9ff9caaee",
  "state": "invalid",
  "message": "The guided-review block does not satisfy the v1 SoftSchema at items.1.references.0.path."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 commit-and-pull
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "e14cf2d1446e0c28e8f103be8d021fe69c95d3c54dc7ccdc11d5d2e8e97873f6",
  "state": "invalid",
  "message": "The guided-review block does not satisfy the v1 SoftSchema at items.1.references.0.pull."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../github_pull_fixture.py" . --describe 7 short-commit
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://github.com/octo/demo/pull/7 --api '/api/plugin/github/guided-review?number=7'
selection: pull_request
pin: 85fcb2fa9e77eb5db485ffef445cbbc645d6db4a (pull request 7 head)
pull_request: 7 (open; fetched 2026-09-17T12:00:00Z by gh:octo-reader)
api: /api/plugin/github/guided-review?number=7
status: 200
{
  "record_revision": "2b982a9c15ef3d15368f831ebe65701b7e459949f32411cd0e7457e7354df853",
  "state": "invalid",
  "message": "The guided-review block does not satisfy the v1 SoftSchema at items.1.references.0.commit."
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
