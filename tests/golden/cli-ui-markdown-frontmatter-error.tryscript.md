---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Front Matter Error Is Shown Once

The server parses a Markdown file’s front matter from the file’s own bytes, on a served
folder and on a pinned revision alike, and when it cannot it names the reason in the
render’s `frontmatter_error` diagnostic (`cli-api-pin-frontmatter.tryscript.md`). KPress
draws its Frontmatter error notice ahead of the document; an inert render’s allowlist
cannot keep that box, so the server takes it out of the inert HTML
(`cli-api-frontmatter-bounds.tryscript.md`) and the page draws the same notice from the
diagnostic (`builtin_plugins/markdown/inert-render.js`).

This browserless session mounts the production Document view, `mountRenderedMarkdown` in
`builtin_plugins/markdown/rendered.js`, with the production wiki preprocessing run in
place of its Worker, over a trusted render, inert renders with and without the
front-matter error, and one whose only diagnostic is that error.
Each document’s preamble, at the top of its prose, holds one notice with the parser’s
reason, lines and all, and the Diagnostics disclosure lists the render’s other
diagnostics only; with no other, there is no disclosure.
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
        "reason": "Error parsing YAML metadata: mapping values are not allowed here\n  in \"<unicode string>\", line 2, column 19:\n    description: Tides: how the harbor office reads it ... \n                      ^ (line: 2)"
      },
      {
        "disclosure": "Diagnostics",
        "listed": [
          "broken_anchor"
        ]
      }
    ],
    "notices": 1
  },
  "inert": {
    "inProse": true,
    "children": [
      {
        "notice": "Frontmatter error",
        "role": "alert",
        "reason": "Error parsing YAML metadata: mapping values are not allowed here\n  in \"<unicode string>\", line 2, column 19:\n    description: Tides: how the harbor office reads it ... \n                      ^ (line: 2)"
      },
      {
        "disclosure": "Diagnostics",
        "listed": [
          "broken_anchor"
        ]
      }
    ],
    "notices": 1
  },
  "inertOnlyFrontmatterError": {
    "inProse": true,
    "children": [
      {
        "notice": "Frontmatter error",
        "role": "alert",
        "reason": "Error parsing YAML metadata: mapping values are not allowed here\n  in \"<unicode string>\", line 2, column 19:\n    description: Tides: how the harbor office reads it ... \n                      ^ (line: 2)"
      }
    ],
    "notices": 1
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
    "notices": 0
  },
  "sentText": {
    "renders": 4,
    "frontMatterAsWritten": true,
    "headingAnchored": true
  }
}
? 0
```
