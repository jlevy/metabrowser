---
cwd: ../..
sandbox: false
---
# Golden Test: The Diagram Frame

Mermaid lays a diagram out in a document before KPress shows it as an image, and there
the diagram’s own CSS can load a URL: its image shape, a `themeCSS` directive, a state
diagram’s `classDef`. A pull request’s description or comment is untrusted on any page,
a folder’s page served trusted among them, so its diagrams are laid out in a frame whose
own Content-Security-Policy loads nothing (`builtin_plugins/markdown/diagram-frame.js`).
That the browser enforces that policy is platform behavior, measured in headless Chrome
by `tests/test_markdown_diagrams_chrome.py`.

This golden pins what Metabrowser decides around it.
The browserless session runs the frame module, the frame’s real entry
(`diagram-frame-entry.js`), and the SDK’s `moduleUrl` (`plugin-sdk-views.js`) as
production code, with a small DOM of its own in which a frame loads a turn after it is
put in the page, and a Mermaid of its own that records what the frame asks of it.
The transcript pins these behaviors:

- The frame’s policy admits its entry and the Mermaid bundle’s directory as scripts,
  inline style, and `data:` images, and nothing else.
- The entry installs one frozen loader.
- The SDK’s `moduleUrl` gives a module bundle’s address, absolute against the page, and
  `null` for a script bundle or an unknown name.
- A lease opens nothing until Mermaid is first asked for; then one frame, hidden from
  the accessibility tree and out of the tab order, whose document is the policy before
  its one script. A second lease shares that frame and its one Mermaid import.
- `initialize` gets the frame’s own copy of the configuration; `render` lays the diagram
  out in a host in the frame’s document carrying the measuring host’s style, returns
  only the SVG text, and removes the host whether it drew or failed.
- The frame stays while any lease holds it.
  The last release removes it, a render in flight then rejects, so KPress’s queue of
  Mermaid calls moves on, and so does a render asked for afterwards; a released lease’s
  `mermaid()` rejects.
- A later lease opens a fresh frame.
- A frame whose entry never ran, a frame released before it loaded, and a page with no
  Mermaid bundle published each reject, and none of them is kept.

```console
$ node tests/dom/markdown-diagram-frame-session.js
{
  "policy": [
    "default-src 'none'",
    "script-src http://127.0.0.1:8000/plugin-static/markdown/0a1b/diagram-frame-entry.js http://127.0.0.1:8000/static/0a1b/vendor/mermaid/",
    "style-src 'unsafe-inline'",
    "img-src data:",
    "base-uri 'none'",
    "form-action 'none'"
  ],
  "entry": {
    "frozen": true,
    "keys": [
      "load"
    ]
  },
  "moduleUrl": {
    "mermaid": "http://127.0.0.1:8000/static/0a1b/vendor/mermaid/mermaid.esm.min.mjs",
    "chart": null,
    "absent": null
  },
  "leases": {
    "framesBeforeAsking": 0,
    "framesWhileLoading": 1,
    "framesWithTwoLeases": 1,
    "secondLeaseSharesTheMermaid": true,
    "askingAgainIsTheSamePromise": true,
    "mermaidImports": [
      "tests/dom/diagram-frame-mermaid-fixture.mjs"
    ],
    "frame": {
      "className": "metabrowser-diagram-frame",
      "tabIndex": -1,
      "ariaHidden": "true",
      "style": {
        "position": "fixed",
        "left": "-100000px",
        "top": "0",
        "width": "1200px",
        "height": "800px",
        "border": "0",
        "visibility": "hidden"
      },
      "policyBeforeScript": true,
      "policy": "default-src 'none'; script-src builtin_plugins/markdown/diagram-frame-entry.js tests/dom/; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'",
      "script": "builtin_plugins/markdown/diagram-frame-entry.js"
    }
  },
  "mermaid": {
    "calls": [
      {
        "initialize": "dark",
        "theFramesOwnCopy": true
      },
      {
        "render": "kpress-diagram-1",
        "text": "flowchart LR; A --> B",
        "hostStyle": "position: fixed; font-family: trebuchet ms; font-size: 16px;",
        "inTheFramesDocument": true
      },
      {
        "render": "kpress-diagram-2",
        "text": "broken",
        "hostStyle": "position: fixed; font-family: trebuchet ms; font-size: 16px;",
        "inTheFramesDocument": true
      }
    ],
    "drawn": {
      "svg": "<svg id=\"kpress-diagram-1\"></svg>"
    },
    "hostsAfterDrawing": 0,
    "broken": {
      "rejected": "Parse error on line 1"
    },
    "hostsAfterFailing": 0
  },
  "release": {
    "framesAfterOneRelease": 1,
    "releasedLeaseAsks": {
      "rejected": "The diagram frame's lease was released"
    },
    "framesAfterTheLast": 0,
    "renderInFlight": {
      "rejected": "The diagram frame closed"
    },
    "afterClosing": {
      "rejected": "The diagram frame closed"
    }
  },
  "reopened": {
    "outcome": {
      "resolved": [
        "initialize",
        "render"
      ]
    },
    "framesEverOpened": 2,
    "framesInPage": 1,
    "mermaidImports": 1
  },
  "failedStarts": {
    "entryMissing": {
      "rejected": "The diagram frame did not start"
    },
    "framesAfterMissing": 0,
    "nextLeaseAfterMissing": {
      "resolved": [
        "initialize",
        "render"
      ]
    },
    "releasedBeforeLoading": {
      "rejected": "The diagram frame closed"
    },
    "noBundle": {
      "rejected": "The Mermaid module bundle is not published"
    },
    "framesOpenedWithNoBundle": 0,
    "framesInPage": 0,
    "mermaidImports": 1
  },
  "failures": []
}
? 0
```
