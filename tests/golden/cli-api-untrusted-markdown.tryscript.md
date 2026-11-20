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
  cp -R "$TRYSCRIPT_TEST_DIR/../fixtures/untrusted-markdown" hostile &&
  cp -R "$TRYSCRIPT_TEST_DIR/../fixtures/github-layout" layout &&
  mkdir slow && (printf '[%.0s' $(seq 1 100); head -c 61440 /dev/zero | tr '\0' '%')
  > slow/slow.md &&
  mkdir diagrams && printf '# Diagrams\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n```svg\n<svg viewBox="0 0 1 1"></svg>\n```\n' > diagrams/README.md
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
  "html": "\n<div><div><h1 id=\"user-content-hostile-readme\">Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"docs/new.md\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><img loading=\"lazy\" src=\"docs/diagram.png\" alt=\"diagram\"> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\">tracker</a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\">image</a> <span>image</span></p>\n<p><a href=\"docs/guide.md\">Guide</a> <a href=\"#user-content-readme\">Top</a> <a href=\"../x.md\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a>api</a> <a>dots</a> <a>escaped</a> <a>debug</a> <a>query</a> <a>raw</a> <span>raw image</span> <a href=\"https://evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<p><a>dotdot</a> <a>dot2e</a> <a>slash</a> <a>back</a> <span>dotimg</span> <span>dot2eimg</span></p>\n<h2 id=\"user-content-section\">Section</h2>\n<p>text</p></div></div>",
  "profile": "document",
  "printable": true,
  "toc": false,
  "inert": true,
? 0
```

The render also names the version of the one repository image it embeds, by the `/raw`
identity the page resolves it to, and the page puts it in that image’s address, so a
replaced image is a new address.
The outside images, links here, get none.

```console
$ grep -A2 '^  "raw_versions":' inert.txt
  "raw_versions": {
    "docs/diagram.png": "[..]"
  }
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
        "id": "css/print-fonts.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-400-normal.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-700-normal.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-400-italic.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-700-italic.css",
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
        "id": "fonts/kpress-quotes.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-370-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-400-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-410-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-550-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-600-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-650-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-370-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-400-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-410-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-550-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-600-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-650-italic.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-400-normal.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-700-normal.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-400-italic.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-700-italic.woff2",
        "loading": "resource"
? 0
```

## Test: an untrusted README keeps GitHub’s layout attributes

`tests/fixtures/github-layout/README.md` lays itself out with the HTML attributes
github.com keeps: Metabrowser’s own README opening, a `width="192"` image in a
`<p align="center">` above an `<h1 align="center">`, then images floated or sized by
`align`, `width`, and `height`, and a table whose cells and rows say how they align.
The inert render keeps each, with its value checked (`ALIGN_VALUES` and `DIMENSIONS` in
`src/metabrowser/inert_html.py`), as KPress’s trusted render keeps it, so the page lays
the document out as github.com does; `tests/test_markdown_github_layout_chrome.py`
measures that in Chrome.
A value that is not a keyword or a number is dropped (`tests/test_inert_html.py`).

```console
$ metab layout --untrusted --api '/api/kpress/render?path=README.md&view=document' > layout.txt
? 0
```

```console
$ grep -E '^  "html":' layout.txt
  "html": "\n<div><div><p align=\"center\"><img loading=\"lazy\" src=\"icon.png\" alt=\"Centered icon\" width=\"192\"></p>\n<h1 id=\"user-content-github-layout\" align=\"center\">GitHub Layout</h1>\n<p align=\"center\">A centered paragraph with a badge <img loading=\"lazy\" src=\"icon.png\" alt=\"Badge\" height=\"20\"> in its text.</p>\n<h2 id=\"user-content-a-right-aligned-image\">A Right-Aligned Image</h2>\n<img loading=\"lazy\" src=\"icon.png\" alt=\"Right icon\" align=\"right\" width=\"120\">\n<p>This paragraph wraps beside an image floated to the right by its <code>align</code> attribute, as\nGitHub draws one, with twenty pixels of room between the image and the text.\nA README puts a project's logo or a screenshot here, beside its introduction, and the\ntext runs down the left side of it until it is past the image's foot.</p>\n<h2 id=\"user-content-a-left-aligned-image\">A Left-Aligned Image</h2>\n<img loading=\"lazy\" src=\"icon.png\" alt=\"Left icon\" align=\"left\" width=\"96\">\n<p>This paragraph wraps beside an image floated to the left, which keeps its room on the\nright, between the image and the text.</p>\n<h2 id=\"user-content-sized-images\">Sized Images</h2>\n<p><img loading=\"lazy\" src=\"icon.png\" alt=\"By width\" width=\"64\"> <img loading=\"lazy\" src=\"icon.png\" alt=\"By height\" height=\"48\"> <img loading=\"lazy\" src=\"icon.png\" alt=\"By both\" width=\"80\" height=\"40\"></p>\n<h2 id=\"user-content-a-table-with-aligned-cells\">A Table With Aligned Cells</h2>\n<div><table>\n  <tbody><tr><th align=\"left\">Left</th><th>Header</th><th align=\"right\">Right</th></tr>\n  <tr><td align=\"center\">Centered</td><td>Default</td><td align=\"right\">Right</td></tr>\n  <tr align=\"right\"><td>Row right</td><td align=\"left\">Cell left</td><td>Row right</td></tr>\n</tbody></table></div>\n<div align=\"right\">A block aligned right.</div>\n<h2 id=\"user-content-a-float-that-ends-the-document\">A Float That Ends the Document</h2>\n<img loading=\"lazy\" src=\"icon.png\" alt=\"Last icon\" align=\"right\" width=\"160\">\n<p>A short last paragraph, beside an image that ends below it.</p></div></div>",
? 0
```

## Test: an untrusted document past the render deadline is refused

Under the untrusted profile a document renders in the server’s Markdown child, under a
deadline (`INERT_RENDER_DEADLINE_MS` in
`src/metabrowser/diff/markdown_projection_worker.py`), and one that runs past it stops
the child and is refused with a code, which the page answers by showing the document’s
source (`cli-ui-markdown-render-refusal.tryscript.md`). `slow/slow.md` is 100 unpaired
`[` before 60 KiB of `%`, which KPress takes seconds to render, so a deadline shortened
to 250 ms through its environment variable refuses it on any machine.
The server says on standard error which document it refused, by its path and the hash it
keeps the refusal by, and after how long; `remembered` is false because this answer is
the render’s own, not a refusal kept from an earlier one.

```console
$ METABROWSER_INERT_RENDER_DEADLINE_MS=250 metab slow --untrusted --api '/api/kpress/render?path=slow.md&view=document'
[..] metabrowser.diff.markdown_projection_worker | Refused rendering 'slow.md' (sha256:6d547e03b6bb237dc4ebdb452e24980c5a74749b35eef82755adf7ab51270c30) after [..] s: render_deadline
api: /api/kpress/render?path=slow.md&view=document
status: 422
{
  "type": "kpress_render_refused",
  "code": "render_deadline",
  "error": "Rendering took longer than 0.25 seconds, so it was stopped",
  "deadline_ms": 250,
  "remembered": false,
  "path": "slow.md"
}
Error: /api/kpress/render?path=slow.md&view=document returned HTTP 422
? 1
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
        "id": "css/print-fonts.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-400-normal.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-700-normal.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-400-italic.css",
        "loading": "stylesheet"
        "id": "css/mono-planetaire-700-italic.css",
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
        "id": "fonts/kpress-quotes.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-370-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-400-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-410-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-550-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-600-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-650-normal.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-370-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-400-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-410-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-550-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-600-italic.woff2",
        "loading": "resource"
        "id": "fonts/kpress-print-sans-latin-650-italic.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-400-normal.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-700-normal.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-400-italic.woff2",
        "loading": "resource"
        "id": "fonts/planetaire-mono-text-latin-700-italic.woff2",
        "loading": "resource"
? 0
```

## Test: a Mermaid diagram survives the allowlist as GitHub’s fallback markup

KPress wraps a `mermaid` fence in a figure whose class and `data-*` the allowlist drops.
The block keeps one attribute instead, `lang="mermaid"`, as GitHub’s own fallback spells
it, so the page draws it, as an image (`builtin_plugins/markdown/diagrams.js`). An `svg`
fence stays code, as GitHub shows it: Metabrowser asks KPress for `diagrams="mermaid"`
(`kpress_adapter.render_kpress_view`).

```console
$ metab diagrams --untrusted --api '/api/kpress/render?path=README.md&view=document' > diagrams-inert.txt
? 0
```

```console
$ grep -E '^  "html":' diagrams-inert.txt
  "html": "\n\n<div><div><h1 id=\"user-content-diagrams\">Diagrams</h1>\n<pre lang=\"mermaid\"><code>flowchart LR\n  A --&gt; B\n</code></pre>\n<pre><code>&lt;svg viewBox=\"0 0 1 1\"&gt;&lt;/svg&gt;\n</code></pre></div></div>",
? 0
```

A trusted render keeps KPress’s Mermaid figure, which the page draws in the document,
and the `svg` fence is still code.

```console
$ metab diagrams --api '/api/kpress/render?path=README.md&view=document' > diagrams-trusted.txt
? 0
```

```console
$ grep -oE 'data-kpress-diagram=\\"[a-z]+\\"' diagrams-trusted.txt
data-kpress-diagram=\"mermaid\"
? 0
```
