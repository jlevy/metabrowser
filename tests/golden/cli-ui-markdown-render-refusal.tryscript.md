---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Refused Markdown Render Shows Its Source

Under the untrusted profile the server renders each Markdown document in its Markdown
child under a deadline (`src/metabrowser/diff/markdown_projection_worker.py`) and
answers a document that ran past it, whose renderer stopped, or whose renderer could not
start with a `kpress_render_refused` envelope and its code, which
`cli-api-untrusted-markdown.tryscript.md` pins from the route.

This browserless session runs the production Document view, `mountRenderedMarkdown` in
`builtin_plugins/markdown/rendered.js`, and the folder Overview’s README panel over the
rejection the SDK makes of each answer, and records what each draws.
`recognized` is which failures are refusals: the three codes, and not a render KPress
itself failed or an abort.
A refused document draws one warning notice saying why and the source in the render’s
place, through the Markdown Source view (front matter and body as two parts), and is no
longer set as a KPress document.
The Document tab of a file the page shows draws the window the page already holds, with
no second read; a window that is not the whole file is said in the notice, which points
to the Source tab, and no Load more is offered beside it.
The README panel, whose README is not the page’s file, keeps its table of contents,
reads the README’s own window from `/api/file`, and links to the file.
A render that failed for another reason keeps the render-error box.

```console
$ node tests/dom/markdown-render-refusal-session.js
{
  "recognized": {
    "render_deadline": {
      "code": "render_deadline",
      "deadlineMs": 5000
    },
    "renderer_exited": {
      "code": "renderer_exited",
      "deadlineMs": 5000
    },
    "renderer_unavailable": {
      "code": "renderer_unavailable",
      "deadlineMs": 5000
    },
    "renderer_busy": {
      "code": "renderer_busy",
      "deadlineMs": 5000
    },
    "kpress_render_error": null,
    "abort": null
  },
  "notes": {
    "render_deadline": "This document took too long to render, so its source is shown.",
    "renderer_exited": "This document could not be rendered, so its source is shown.",
    "renderer_unavailable": "This document could not be rendered, so its source is shown. Reload to try again.",
    "renderer_busy": "This document could not be rendered, so its source is shown. Reload to try again.",
    "shortened": "This document took too long to render, so its source is shown."
  },
  "documentTab": {
    "classes": [
      "content-body",
      "md-body"
    ],
    "markup": "<div class=\"notice metabrowser-render-refused\" data-severity=\"warning\" role=\"status\" data-refusal=\"render_deadline\">This document took too long to render, so its source is shown.</div><div class=\"metabrowser-render-refused-source\"></div>",
    "renderError": false,
    "renders": [
      {
        "path": "slow.md",
        "view": "rendered",
        "includeToc": null
      }
    ],
    "completeText": [],
    "fetched": [],
    "sources": [
      {
        "path": "slow.md",
        "ext": ".md",
        "content": "---\ntitle: Slow\n---\n[[[[[[[[%%%%%%%%%%%%%%%%%%%%%%%%\n",
        "continues": false,
        "parts": [
          "yaml",
          "markdown"
        ]
      }
    ]
  },
  "partialWindow": {
    "classes": [
      "content-body",
      "md-body"
    ],
    "markup": "<div class=\"notice metabrowser-render-refused\" data-severity=\"warning\" role=\"status\" data-refusal=\"render_deadline\">This document took too long to render, so its source is shown. Showing the first 10 B of 4096 B; the Source tab shows the rest.</div><div class=\"metabrowser-render-refused-source\"></div>",
    "renderError": false,
    "renders": [
      {
        "path": "slow.md",
        "view": "rendered",
        "includeToc": null
      }
    ],
    "completeText": [
      "slow.md"
    ],
    "fetched": [],
    "sources": [
      {
        "path": "slow.md",
        "ext": ".md",
        "content": "# Partial\n",
        "continues": false,
        "parts": []
      }
    ]
  },
  "otherCodes": {
    "renderer_exited": {
      "markup": "<div class=\"notice metabrowser-render-refused\" data-severity=\"warning\" role=\"status\" data-refusal=\"renderer_exited\">This document could not be rendered, so its source is shown.</div><div class=\"metabrowser-render-refused-source\"></div>",
      "renderError": false
    },
    "renderer_unavailable": {
      "markup": "<div class=\"notice metabrowser-render-refused\" data-severity=\"warning\" role=\"status\" data-refusal=\"renderer_unavailable\">This document could not be rendered, so its source is shown. Reload to try again.</div><div class=\"metabrowser-render-refused-source\"></div>",
      "renderError": false
    },
    "renderer_busy": {
      "markup": "<div class=\"notice metabrowser-render-refused\" data-severity=\"warning\" role=\"status\" data-refusal=\"renderer_busy\">This document could not be rendered, so its source is shown. Reload to try again.</div><div class=\"metabrowser-render-refused-source\"></div>",
      "renderError": false
    }
  },
  "renderFailure": {
    "renderError": true,
    "sources": [],
    "logged": [
      "metabrowser: the document could not be rendered · KPress render failed"
    ]
  },
  "readmePanel": {
    "classes": [
      "folder-overview-panel-document"
    ],
    "markup": "<div class=\"notice metabrowser-render-refused\" data-severity=\"warning\" role=\"status\" data-refusal=\"render_deadline\">This document took too long to render, so its source is shown. Showing the first 19 B of 9000 B. <a class=\"metabrowser-render-refused-open\" href=\"/view/README.md\">Open the file</a></div><div class=\"metabrowser-render-refused-source\"></div>",
    "renderError": false,
    "renders": [
      {
        "path": "README.md",
        "view": "rendered",
        "includeToc": null
      }
    ],
    "completeText": [],
    "fetched": [
      "/api/file?path=README.md"
    ],
    "sources": [
      {
        "path": "README.md",
        "ext": ".md",
        "content": "# Readme\n\n[[[[%%%%\n",
        "continues": false,
        "parts": []
      }
    ]
  }
}
? 0
```
