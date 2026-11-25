---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Front Matter Error Is Shown Once

The server parses a Markdown file’s front matter from the file’s own bytes, on a served
folder and on a pinned revision alike, and when it cannot its render’s
`frontmatter_error` diagnostic says so in a sentence for the reader, with the parser’s
reason beside it in `frontmatter_error_detail` (`cli-api-pin-frontmatter.tryscript.md`).
KPress draws its Frontmatter error notice ahead of the document; an inert render’s
allowlist cannot keep that box, so the server takes it out of the inert HTML
(`cli-api-frontmatter-bounds.tryscript.md`) and the page draws the same notice from the
diagnostic (`builtin_plugins/markdown/inert-render.js`).

This browserless session mounts the production Document view, `mountRenderedMarkdown` in
`builtin_plugins/markdown/rendered.js`, with the production wiki preprocessing run in
place of its Worker, over a trusted render, inert renders with and without the
front-matter error, and one whose only diagnostic is that error.
Each document’s preamble, at the top of its prose, holds one notice with that sentence
and not the parser’s reason (`detailShown`), and the Diagnostics disclosure lists the
render’s other diagnostics only; with no other, there is no disclosure.
`sentText` is what the view sent to render: the front matter as the file has it, with
the heading’s anchor written into the body only.

```console
$ node tests/dom/markdown-frontmatter-error-session.js
{
  "trusted": {
    "inProse": true,
    "children": [
      {
        "notice": "Frontmatter error",
        "role": "alert",
        "reason": "The frontmatter could not be read."
      },
      {
        "disclosure": "Diagnostics",
        "listed": [
          "broken_anchor"
        ]
      }
    ],
    "notices": 1,
    "detailShown": false
  },
  "inert": {
    "inProse": true,
    "children": [
      {
        "notice": "Frontmatter error",
        "role": "status",
        "reason": "The frontmatter could not be read."
      },
      {
        "disclosure": "Diagnostics",
        "listed": [
          "broken_anchor"
        ]
      }
    ],
    "notices": 1,
    "detailShown": false
  },
  "inertOnlyFrontmatterError": {
    "inProse": true,
    "children": [
      {
        "notice": "Frontmatter error",
        "role": "status",
        "reason": "The frontmatter could not be read."
      }
    ],
    "notices": 1,
    "detailShown": false
  },
  "inertWithoutFrontmatterError": {
    "inProse": true,
    "children": [
      {
        "disclosure": "Diagnostics",
        "listed": [
          "broken_anchor"
        ]
      }
    ],
    "notices": 0,
    "detailShown": false
  },
  "sentText": {
    "renders": 4,
    "frontMatterAsWritten": true,
    "headingAnchored": true
  }
}
? 0
```
