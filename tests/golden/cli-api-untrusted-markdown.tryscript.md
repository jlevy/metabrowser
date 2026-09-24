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

The render is marked `inert`, and every tag and attribute left in its HTML is one the
allowlist keeps: plain text markup, links (`href`, and `target` and `rel` on one that
leaves the page), the repository image (`src`, `alt`), and each heading’s
`user-content-` anchor (`id`), which the hardener makes from the heading’s text.

```console
$ metab hostile --untrusted --api '/api/kpress/render?path=README.md&view=document' | grep -E '^  "inert":'
  "inert": true
? 0
```

```console
$ metab hostile --untrusted --api '/api/kpress/render?path=README.md&view=document' | grep -E '^  "html":' | grep -oE '<[a-z0-9]+|[ ][a-z-]+=' | sort -u
 alt=
 href=
 id=
 rel=
 src=
 target=
<a
<code
<div
<h1
<h2
<img
<p
<span
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
