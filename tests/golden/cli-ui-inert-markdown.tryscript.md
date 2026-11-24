---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Inert Markdown

Markdown from an untrusted source -- a mirrored repository’s documents, a folder served
with `--untrusted`, and every pull-request comment -- reaches the page only through the
allowlist in `static/inert-html.js`, the same as `src/metabrowser/inert_html.py` applies
on the server. The page parses a render into an inert template and inserts only nodes
rebuilt from the allowlist: plain text markup, links, and images inside the served tree
or from the web over `https`, with no class, `name`, `data-*`, style, or event attribute
but the image fallback’s own, no `id` the document wrote, and no SVG, MathML, media,
stylesheet, frame, form, or input but a disabled checkbox in the shape of a task list’s
box, wherever the document writes one.

This browserless session loads the production `static/inert-html.js` and
`builtin_plugins/markdown/inert-render.js`, and rebuilds KPress’s render of
`tests/fixtures/untrusted-markdown/README.md`, recorded as Python’s HTML parse of it in
`tests/fixtures/inert-html-kpress-tree.json`. A document inside the served tree keeps
its own references and images as written, for the page to resolve inside the root or
pin, and gives every kept image `loading="lazy"`, whatever the document wrote.
An image from the web is kept when the document writes its address in full over `https`,
with `referrerpolicy="no-referrer"`, in a document and in a pull-request comment alike,
so a README’s badges show as they do on github.com.
Any other image, such as one over `http`, is its alt text in a span of the class
`mb-image-fallback`, with the address it would have loaded in its `data-tip-text`:
inside the link the image was in, which keeps its own destination, so a badge is never
an empty link followed by a link to its image, and otherwise inside a link to the image.
`prose` is what `kpressProse` builds for a page to set those nodes in: KPress’s two
wrappers dropped, and a code block and a table given the classes KPress’s stylesheets
hang their type on, chosen by element and never from the document.
`alignedProse` is a document whose one block is its own `<div align="center">`: the
unwrapping stops at a `<div>` with an attribute, so the document keeps its alignment.
Its headings get the anchors github.com gives them (`user-content-` and the slug of the
heading’s text, as `hostile-readme`), and its fragment links reach them (`#readme`
becomes `#user-content-readme`). A pull-request comment makes every reference absolute
against the pull request’s github.com page, keeps no image of its own, which names no
tree, so a path is a link to where it would be, and has no anchors.
`blocked` is the same two renders when the reader has ticked **Block remote images**
(`METABROWSER_SETTINGS.BLOCK_REMOTE_IMAGES`): every image from the web is its fallback,
in the link it was in or in a link to the image, and the document’s own image still
loads.
`badges` is a hand-built row of them, which the fixture’s tree is too long to hold
each of: an image in a link over `https` and over `http`, one in no link in each, one in
a link to GitHub, and one in a link to a file of the tree, in a document, in a comment,
and with the setting on.
`fallbacks` is what the page keeps of a span the server did not write as the fallback:
the class exactly, with an address that is `http` or `https` for the tooltip, and
nothing else.
The session fails if a node outside the allowlist would be inserted, a link
would hold another, or an image from the web would be fetched with a referrer.

KPress removes a link whose scheme is not `http` or `https` before the allowlist sees
it, so the README cannot show what the allowlist itself does with one.
`links` is its answer to `tests/fixtures/inert-html-hostile-links.json`, handed to it
directly in both modes: a `javascript:`, `data:`, or other such link, however it is
spelled, keeps its text and loses its address.
`tests/test_inert_html.py` hands the server’s side the same links.

```console
$ node tests/dom/inert-html-session.js
{
  "inertRender": {
    "inert": true,
    "trusted": false
  },
  "document": "\n<div><div><h1 id=\"user-content-hostile-readme\">Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"docs/new.md\">the docs</a>.</p>\n\n<img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/badge.png\" alt=\"build badge\"> <span class=\"mb-image-fallback\">image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><img loading=\"lazy\" src=\"docs/diagram.png\" alt=\"diagram\"> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/t.gif\" alt=\"tracker\"> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/p.gif\"> <span class=\"mb-image-fallback\">image</span></p>\n<p><a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/follow-%40ojoshe-black\" alt=\"Follow @ojoshe on X\"></a> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/standalone-blue\" alt=\"standalone\"></p>\n<p><a href=\"docs/guide.md\">Guide</a> <a href=\"#user-content-readme\">Top</a> <a href=\"../x.md\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a>api</a> <a>dots</a> <a>escaped</a> <a>debug</a> <a>query</a> <a>raw</a> <span class=\"mb-image-fallback\">raw image</span> <a href=\"https://evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<p><a>dotdot</a> <a>dot2e</a> <a>slash</a> <a>back</a> <span class=\"mb-image-fallback\">dotimg</span> <span class=\"mb-image-fallback\">dot2eimg</span></p>\n<h2 id=\"user-content-section\">Section</h2>\n<p>text</p></div></div>",
  "comment": "\n<div><div><h1>Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/badge.png\" alt=\"build badge\"> <span class=\"mb-image-fallback\">image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><a href=\"https://github.com/octo/demo/pull/docs/diagram.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/octo/demo/pull/docs/diagram.png\">diagram</span></a> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/t.gif\" alt=\"tracker\"> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/p.gif\"> <span class=\"mb-image-fallback\">image</span></p>\n<p><a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/follow-%40ojoshe-black\" alt=\"Follow @ojoshe on X\"></a> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/standalone-blue\" alt=\"standalone\"></p>\n<p><a href=\"https://github.com/octo/demo/pull/docs/guide.md\" target=\"_blank\" rel=\"noopener noreferrer\">Guide</a> <a href=\"https://github.com/octo/demo/pull/7#readme\" target=\"_blank\" rel=\"noopener noreferrer\">Top</a> <a href=\"https://github.com/octo/demo/x.md\" target=\"_blank\" rel=\"noopener noreferrer\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\">api</a> <a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\">dots</a> <a href=\"https://github.com/%61pi/tree\" target=\"_blank\" rel=\"noopener noreferrer\">escaped</a> <a href=\"https://github.com/_debug/tasks\" target=\"_blank\" rel=\"noopener noreferrer\">debug</a> <a href=\"https://github.com/octo/demo/pull/7?q=1\" target=\"_blank\" rel=\"noopener noreferrer\">query</a> <a href=\"https://github.com/raw?path=evil.html\" target=\"_blank\" rel=\"noopener noreferrer\">raw</a> <a href=\"https://github.com/raw?path=x.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/raw?path=x.png\">raw image</span></a> <a href=\"https://github.com/octo/demo/pull/evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://github.com/one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<p><a href=\"https://github.com/raw?path=evil.js\" target=\"_blank\" rel=\"noopener noreferrer\">dotdot</a> <a href=\"https://github.com/raw?x\" target=\"_blank\" rel=\"noopener noreferrer\">dot2e</a> <a href=\"https://github.com/api%2ftree\" target=\"_blank\" rel=\"noopener noreferrer\">slash</a> <a href=\"https://github.com/%5capi/tree\" target=\"_blank\" rel=\"noopener noreferrer\">back</a> <a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/api/tree\">dotimg</span></a> <a href=\"https://github.com/raw?path=x.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/raw?path=x.png\">dot2eimg</span></a></p>\n<h2>Section</h2>\n<p>text</p></div></div>",
  "blocked": {
    "document": "\n<div><div><h1 id=\"user-content-hostile-readme\">Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"docs/new.md\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/badge.png\">build badge</span></a> <span class=\"mb-image-fallback\">image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><img loading=\"lazy\" src=\"docs/diagram.png\" alt=\"diagram\"> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/t.gif\">tracker</span></a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/p.gif\">image</span></a> <span class=\"mb-image-fallback\">image</span></p>\n<p><a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/follow-%40ojoshe-black\">Follow @ojoshe on X</span></a> <a href=\"https://img.shields.io/badge/standalone-blue\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/standalone-blue\">standalone</span></a></p>\n<p><a href=\"docs/guide.md\">Guide</a> <a href=\"#user-content-readme\">Top</a> <a href=\"../x.md\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a>api</a> <a>dots</a> <a>escaped</a> <a>debug</a> <a>query</a> <a>raw</a> <span class=\"mb-image-fallback\">raw image</span> <a href=\"https://evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<p><a>dotdot</a> <a>dot2e</a> <a>slash</a> <a>back</a> <span class=\"mb-image-fallback\">dotimg</span> <span class=\"mb-image-fallback\">dot2eimg</span></p>\n<h2 id=\"user-content-section\">Section</h2>\n<p>text</p></div></div>",
    "comment": "\n<div><div><h1>Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/badge.png\">build badge</span></a> <span class=\"mb-image-fallback\">image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><a href=\"https://github.com/octo/demo/pull/docs/diagram.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/octo/demo/pull/docs/diagram.png\">diagram</span></a> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/t.gif\">tracker</span></a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/p.gif\">image</span></a> <span class=\"mb-image-fallback\">image</span></p>\n<p><a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/follow-%40ojoshe-black\">Follow @ojoshe on X</span></a> <a href=\"https://img.shields.io/badge/standalone-blue\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/standalone-blue\">standalone</span></a></p>\n<p><a href=\"https://github.com/octo/demo/pull/docs/guide.md\" target=\"_blank\" rel=\"noopener noreferrer\">Guide</a> <a href=\"https://github.com/octo/demo/pull/7#readme\" target=\"_blank\" rel=\"noopener noreferrer\">Top</a> <a href=\"https://github.com/octo/demo/x.md\" target=\"_blank\" rel=\"noopener noreferrer\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\">api</a> <a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\">dots</a> <a href=\"https://github.com/%61pi/tree\" target=\"_blank\" rel=\"noopener noreferrer\">escaped</a> <a href=\"https://github.com/_debug/tasks\" target=\"_blank\" rel=\"noopener noreferrer\">debug</a> <a href=\"https://github.com/octo/demo/pull/7?q=1\" target=\"_blank\" rel=\"noopener noreferrer\">query</a> <a href=\"https://github.com/raw?path=evil.html\" target=\"_blank\" rel=\"noopener noreferrer\">raw</a> <a href=\"https://github.com/raw?path=x.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/raw?path=x.png\">raw image</span></a> <a href=\"https://github.com/octo/demo/pull/evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://github.com/one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<p><a href=\"https://github.com/raw?path=evil.js\" target=\"_blank\" rel=\"noopener noreferrer\">dotdot</a> <a href=\"https://github.com/raw?x\" target=\"_blank\" rel=\"noopener noreferrer\">dot2e</a> <a href=\"https://github.com/api%2ftree\" target=\"_blank\" rel=\"noopener noreferrer\">slash</a> <a href=\"https://github.com/%5capi/tree\" target=\"_blank\" rel=\"noopener noreferrer\">back</a> <a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/api/tree\">dotimg</span></a> <a href=\"https://github.com/raw?path=x.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/raw?path=x.png\">dot2eimg</span></a></p>\n<h2>Section</h2>\n<p>text</p></div></div>"
  },
  "badges": {
    "document": "<a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/a-b\" alt=\"Linked\"></a> <a href=\"https://github.com/octo/demo/actions/workflows/ci.yml\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://github.com/octo/demo/actions/workflows/ci.yml/badge.svg\" alt=\"CI\"></a> <a href=\"https://example.com/dest\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"http://example.com/insecure.png\">Linked over http</span></a> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/c-d\" alt=\"Standalone\"> <a href=\"http://example.com/plain.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"http://example.com/plain.png\">Plain over http</span></a> <a href=\"docs/guide.md\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/e-f\"></a>",
    "comment": "<a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/a-b\" alt=\"Linked\"></a> <a href=\"https://github.com/octo/demo/actions/workflows/ci.yml\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://github.com/octo/demo/actions/workflows/ci.yml/badge.svg\" alt=\"CI\"></a> <a href=\"https://example.com/dest\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"http://example.com/insecure.png\">Linked over http</span></a> <img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/c-d\" alt=\"Standalone\"> <a href=\"http://example.com/plain.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"http://example.com/plain.png\">Plain over http</span></a> <a href=\"https://github.com/octo/demo/pull/docs/guide.md\" target=\"_blank\" rel=\"noopener noreferrer\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://img.shields.io/badge/e-f\"></a>",
    "blocked": "<a href=\"https://x.com/ojoshe\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/a-b\">Linked</span></a> <a href=\"https://github.com/octo/demo/actions/workflows/ci.yml\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://github.com/octo/demo/actions/workflows/ci.yml/badge.svg\">CI</span></a> <a href=\"https://example.com/dest\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"http://example.com/insecure.png\">Linked over http</span></a> <a href=\"https://img.shields.io/badge/c-d\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/c-d\">Standalone</span></a> <a href=\"http://example.com/plain.png\" target=\"_blank\" rel=\"noopener noreferrer\"><span class=\"mb-image-fallback\" data-tip-text=\"http://example.com/plain.png\">Plain over http</span></a> <a href=\"docs/guide.md\"><span class=\"mb-image-fallback\" data-tip-text=\"https://img.shields.io/badge/e-f\">image</span></a>"
  },
  "fallbacks": "<span class=\"mb-image-fallback\" data-tip-text=\"https://example.com/a.png\">valid</span><span class=\"mb-image-fallback\">no address</span><span class=\"mb-image-fallback\">bad address</span><span class=\"mb-image-fallback\">relative address</span><span>other class</span><span class=\"mb-image-fallback\">extras</span><span>no class</span>",
  "prose": {
    "div.kpress-prose": [
      {
        "h1": []
      },
      {
        "pre.kpress-code": [
          {
            "code": []
          }
        ]
      },
      {
        "div.kpress-table-wrap": [
          {
            "table.kpress-table": []
          }
        ]
      }
    ]
  },
  "alignedProse": {
    "div.kpress-prose": [
      {
        "div[align=center]": [
          {
            "h1": []
          }
        ]
      }
    ]
  },
  "links": {
    "document": "<a>script</a><a>mixed case</a><a>padded</a><a>split</a><a>control</a><a>data</a><a>vbscript</a><a>file</a><a>blob</a><a>mailto</a><a>ftp</a><a>websocket</a><a>view-source</a><a href=\"https://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">https</a><a href=\"http://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">http</a><a href=\"http://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">mixed-case scheme</a><a href=\"http://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">mixed-case scheme with a CR in it</a>",
    "comment": "<a>script</a><a>mixed case</a><a>padded</a><a>split</a><a>control</a><a>data</a><a>vbscript</a><a>file</a><a>blob</a><a>mailto</a><a>ftp</a><a>websocket</a><a>view-source</a><a href=\"https://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">https</a><a href=\"http://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">http</a><a href=\"http://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">mixed-case scheme</a><a href=\"http://example.com/ok\" target=\"_blank\" rel=\"noopener noreferrer\">mixed-case scheme with a CR in it</a>"
  },
  "kpressRemoved": ""
}
? 0
```
