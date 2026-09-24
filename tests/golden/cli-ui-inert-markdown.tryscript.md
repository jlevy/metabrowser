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
rebuilt from the allowlist: plain text markup, links, and images inside the served tree,
with no class, `id`, `name`, `data-*`, style, or event attribute, and no SVG, MathML,
media, stylesheet, frame, or form.

This browserless session loads the production `static/inert-html.js` and
`builtin_plugins/markdown/inert-render.js`, and rebuilds KPress’s render of
`tests/fixtures/untrusted-markdown/README.md`, recorded as Python’s HTML parse of it in
`tests/fixtures/inert-html-kpress-tree.json`. A document inside the served tree keeps
its own references and images as written, for the page to resolve inside the root or
pin, and turns outside images into links; a pull-request comment makes every reference
absolute against the pull request’s github.com page and every image a link.
The session fails if a node outside the allowlist would be inserted.

```console
$ node tests/dom/inert-html-session.js
{
  "inertRender": {
    "inert": true,
    "trusted": false
  },
  "document": "\n<div><div><h1>Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"docs/new.md\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><img src=\"docs/diagram.png\" alt=\"diagram\"> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\">tracker</a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\">image</a> <span>image</span></p>\n<p><a href=\"docs/guide.md\">Guide</a> <a href=\"#readme\">Top</a> <a href=\"../x.md\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a>api</a> <a>dots</a> <a>escaped</a> <a>debug</a> <a>query</a> <a>raw</a> <span>raw image</span> <a href=\"https://evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<h2>Section</h2>\n<p>text</p></div></div>",
  "comment": "\n<div><div><h1>Hostile readme</h1>\n<p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n\n<p><a href=\"https://github.com/octo/demo/pull/docs/diagram.png\" target=\"_blank\" rel=\"noopener noreferrer\">diagram</a> <a href=\"https://example.com/t.gif\" target=\"_blank\" rel=\"noopener noreferrer\">tracker</a> <a href=\"https://example.com/p.gif\" target=\"_blank\" rel=\"noopener noreferrer\">image</a> <span>image</span></p>\n<p><a href=\"https://github.com/octo/demo/pull/docs/guide.md\" target=\"_blank\" rel=\"noopener noreferrer\">Guide</a> <a href=\"https://github.com/octo/demo/pull/7#readme\" target=\"_blank\" rel=\"noopener noreferrer\">Top</a> <a href=\"https://github.com/octo/demo/x.md\" target=\"_blank\" rel=\"noopener noreferrer\">Up</a> <a>tab</a> <a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">slashes</a></p>\n<p><a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\">api</a> <a href=\"https://github.com/api/tree\" target=\"_blank\" rel=\"noopener noreferrer\">dots</a> <a href=\"https://github.com/%61pi/tree\" target=\"_blank\" rel=\"noopener noreferrer\">escaped</a> <a href=\"https://github.com/_debug/tasks\" target=\"_blank\" rel=\"noopener noreferrer\">debug</a> <a href=\"https://github.com/octo/demo/pull/7?q=1\" target=\"_blank\" rel=\"noopener noreferrer\">query</a> <a href=\"https://github.com/raw?path=evil.html\" target=\"_blank\" rel=\"noopener noreferrer\">raw</a> <a href=\"https://github.com/raw?path=x.png\" target=\"_blank\" rel=\"noopener noreferrer\">raw image</a> <a href=\"https://github.com/octo/demo/pull/evil.test/no-slashes\" target=\"_blank\" rel=\"noopener noreferrer\">bare</a> <a href=\"https://github.com/one.test/x\" target=\"_blank\" rel=\"noopener noreferrer\">one slash</a></p>\n<h2>Section</h2>\n<p>text</p></div></div>"
}
? 0
```
