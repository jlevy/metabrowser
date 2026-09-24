---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  cp -R "$TRYSCRIPT_TEST_DIR/../fixtures/untrusted-markdown" hostile
---
# Golden Test: Markdown From an Untrusted Source

`tests/fixtures/untrusted-markdown/README.md` carries every payload of the hostile
corpus in `tests/github_pull_fixture.py` and `tests/test_inert_html.py`: a stylesheet
link, styles, outside and `data:` images, SVG paint servers and filters with `url()`,
SVG `<use>` and SMIL, `data-kpress-video-id`, `data-mb-copy`, `data-nav-dir`,
`class="modal-overlay"`, `id` and `name`, `ping` and `attributionsrc`, a form, a frame,
a video, a script, and obfuscated `javascript:` links, beside ordinary Markdown with a
repository image and relative links.

Under the untrusted profile -- every served mirror, and a folder served with
`--untrusted` -- the Markdown route answers the document reduced to the inert allowlist
(`src/metabrowser/inert_html.py`), marks it `inert`, and sends no KPress script: only
stylesheets and the files they use stay in its assets.

## Test: an untrusted README renders inert

```console
$ metab hostile --untrusted --api '/api/kpress/render?path=README.md&view=document' | grep -E '^  "(html|inert)":'
  "html": "\n<div><div><h1>Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"docs/new.md\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><img src=\"docs/diagram.png\" alt=\"diagram\"> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\">tracker</a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\">image</a> <span>image</span></p>\n<p><a href=\"docs/guide.md\">Guide</a> <a href=\"#readme\">Top</a> <a href=\"../x.md\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<h2>Section</h2>\n<p>text</p></div></div>",
  "inert": true
? 0
```

```console
$ metab hostile --untrusted --api '/api/kpress/render?path=README.md&view=document' | grep -E '"loading":' | sort -u
        "loading": "resource"
        "loading": "stylesheet"
? 0
```

## Test: a trusted folder keeps KPress’s rich render

The same document in a folder served as trusted keeps KPress’s markup, its classes, and
the video entry point its `data-kpress-video-id` asks for.

```console
$ metab hostile --api '/api/kpress/render?path=README.md&view=document' | grep -cE 'data-kpress-video-id|kpress-prose'
1
? 0
```
