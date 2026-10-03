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

The render is marked `inert`, and its HTML is the document reduced to the allowlist:
plain text markup, links (`href`, and `target` and `rel` on one that leaves the page),
the repository image (`src`, `alt`), and each heading’s `user-content-` anchor (`id`),
which the hardener makes from the heading’s text.
The envelope goes to a file, and its `html` is then shown whole, so each attribute is
pinned with its value: a `javascript:` link, an outside image, or a `data:` URL that
survived would be in this line.

```console
$ metab hostile --untrusted --api '/api/kpress/render?path=README.md&view=document' > inert.txt
? 0
```

```console
$ grep -E '^  "(type|html|profile|printable|toc|inert)":' inert.txt
  "type": "kpress-rendered-document",
  "html": "\n<div><div><h1 id=\"user-content-hostile-readme\">Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"docs/new.md\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><img src=\"docs/diagram.png\" alt=\"diagram\"> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\">tracker</a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\">image</a> <span>image</span></p>\n<p><a href=\"docs/guide.md\">Guide</a> <a href=\"#user-content-readme\">Top</a> <a href=\"../x.md\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a>api</a> <a>dots</a> <a>escaped</a> <a>debug</a> <a>query</a> <a>raw</a> <span>raw image</span> <a href=\"https://evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<p><a>dotdot</a> <a>dot2e</a> <a>slash</a> <a>back</a> <span>dotimg</span> <span>dot2eimg</span></p>\n<h2 id=\"user-content-section\">Section</h2>\n<p>text</p></div></div>",
  "profile": "document",
  "printable": true,
  "toc": false,
  "inert": true
? 0
```

Every asset the inert render asks for is a stylesheet or a file a stylesheet uses.
None is a script.

```console
$ grep -E '^        "(id|loading)":' inert.txt
        "id": "css/style-tokens.css",
        "loading": "stylesheet"
        "id": "css/syntax.css",
        "loading": "stylesheet"
        "id": "css/document.css",
        "loading": "stylesheet"
        "id": "css/components.css",
        "loading": "stylesheet"
        "id": "css/print.css",
        "loading": "stylesheet"
        "id": "fonts/pt-serif-latin-400-normal.woff2",
        "loading": "resource"
        "id": "fonts/pt-serif-latin-700-normal.woff2",
        "loading": "resource"
        "id": "fonts/pt-serif-latin-400-italic.woff2",
        "loading": "resource"
        "id": "fonts/pt-serif-latin-700-italic.woff2",
        "loading": "resource"
        "id": "fonts/source-sans-3-latin-wght-normal.woff2",
        "loading": "resource"
        "id": "fonts/source-sans-3-latin-wght-italic.woff2",
        "loading": "resource"
? 0
```

## Test: a trusted folder keeps KPress’s rich render

The same document in a folder served as trusted keeps KPress’s markup and its classes,
and asks for KPress’s scripts, the video popover its `data-kpress-video-id` needs among
them.

```console
$ metab hostile --api '/api/kpress/render?path=README.md&view=document' > rich.txt
? 0
```

```console
$ grep -oE 'class=\\"kpress-prose[^\\]*\\"|data-kpress-video-id=\\"[^\\]*\\"' rich.txt
class=\"kpress-prose kpress-long-text\"
data-kpress-video-id=\"dQw4w9WgXcQ\"
? 0
```

```console
$ grep -E '^        "(id|loading)":' rich.txt
        "id": "css/style-tokens.css",
        "loading": "stylesheet"
        "id": "css/syntax.css",
        "loading": "stylesheet"
        "id": "css/document.css",
        "loading": "stylesheet"
        "id": "css/components.css",
        "loading": "stylesheet"
        "id": "css/print.css",
        "loading": "stylesheet"
        "id": "js/runtime.js",
        "loading": "module"
        "id": "js/tooltips.js",
        "loading": "module"
        "id": "js/history.js",
        "loading": "module"
        "id": "js/video-popover.js",
        "loading": "module"
        "id": "js/overlay.js",
        "loading": "module"
        "id": "js/viewport.js",
        "loading": "module"
        "id": "fonts/pt-serif-latin-400-normal.woff2",
        "loading": "resource"
        "id": "fonts/pt-serif-latin-700-normal.woff2",
        "loading": "resource"
        "id": "fonts/pt-serif-latin-400-italic.woff2",
        "loading": "resource"
        "id": "fonts/pt-serif-latin-700-italic.woff2",
        "loading": "resource"
        "id": "fonts/source-sans-3-latin-wght-normal.woff2",
        "loading": "resource"
        "id": "fonts/source-sans-3-latin-wght-italic.woff2",
        "loading": "resource"
? 0
```
