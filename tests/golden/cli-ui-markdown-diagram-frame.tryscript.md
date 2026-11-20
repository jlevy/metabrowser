---
cwd: ../..
sandbox: false
---
# Golden Test: The Diagram Frame

Mermaid lays a diagram out in a document before KPress shows it as an image, and there
the diagram’s own CSS can load a URL: its image shape, a `themeCSS` directive, a state
diagram’s `classDef`, among others.
A pull request’s description or comment is untrusted on any page, a folder’s page served
trusted among them, so its diagrams are laid out in a frame whose own
Content-Security-Policy loads nothing (`builtin_plugins/markdown/diagram-frame.js`).
That the browser enforces that policy is platform behavior, measured in headless Chrome
by `tests/test_markdown_diagrams_chrome.py`, which also checks that the frame lays a
diagram out at the page’s size and that a frame taken out mid-draw holds nothing up.

This golden pins what Metabrowser decides around it.
The browserless session runs the frame module, the frame’s real entry
(`diagram-frame-entry.js`), the SDK’s `moduleUrl` (`plugin-sdk-views.js`), and the asset
loader’s `ensureModule` (`asset-loader.js`) as production code, with a small DOM of its
own in which a frame loads a turn after it is put in the page, and a Mermaid of its own
that records what the frame asks of it.
The transcript pins these behaviors:

- The frame’s policy admits its entry and the Mermaid bundle’s directory as scripts, its
  stylesheet and inline style, and `data:` images, and nothing else.
- The entry installs one frozen loader.
- The SDK’s `moduleUrl` gives a module bundle’s address, absolute against the page, and
  `null` for a script bundle or an unknown name.
  It reads each shape of bundle as `ensureModule` does: it gives an address for exactly
  the names `ensureModule` would import.
- A lease opens nothing until Mermaid is first asked for; then one frame, sandboxed to
  scripts and its origin, hidden from the accessibility tree and out of the tab order,
  whose document is the policy, then its stylesheet, then its one script.
  A second lease shares that frame and its one Mermaid import.
- `initialize` gets the frame’s own copy of the configuration; `render` lays the diagram
  out in a host in the frame’s document carrying the measuring host’s style, returns
  only the SVG text, and removes the host whether it drew or failed.
  An image shape that fails says its image is not loaded.
- The frame stays while any lease holds it.
  The last release removes it, and a render in flight then rejects, so KPress’s queue of
  Mermaid calls moves on; a released lease’s `mermaid()`, and its Mermaid’s `render`,
  reject.
- A later lease opens a fresh frame.
- A frame taken out of the page or navigated away closes as the last release does: a
  render in flight rejects, and the lease’s next render opens a new frame and gives it
  the binding’s configuration.
- A frame whose entry never ran, a frame released or taken out before it loaded, and a
  page with no Mermaid bundle published each reject, and none of them is kept.

```console
$ node tests/dom/markdown-diagram-frame-session.js
{
  "policy": [
    "default-src 'none'",
    "script-src http://127.0.0.1:8000/plugin-static/markdown/0a1b/diagram-frame-entry.js http://127.0.0.1:8000/static/0a1b/vendor/mermaid/",
    "style-src http://127.0.0.1:8000/plugin-static/markdown/0a1b/diagram-frame.css 'unsafe-inline'",
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
  "moduleUrlAgreesWithEnsureModule": {
    "module": {
      "moduleUrl": "http://127.0.0.1:8000/static/m.mjs",
      "ensureModuleImports": true
    },
    "script": {
      "moduleUrl": null,
      "ensureModuleImports": false
    },
    "twoEntries": {
      "moduleUrl": null,
      "ensureModuleImports": false
    },
    "notAString": {
      "moduleUrl": null,
      "ensureModuleImports": false
    },
    "emptyModule": {
      "moduleUrl": null,
      "ensureModuleImports": false
    },
    "nullEntry": {
      "moduleUrl": null,
      "ensureModuleImports": false
    },
    "notAList": {
      "moduleUrl": null,
      "ensureModuleImports": false
    },
    "absent": {
      "moduleUrl": null,
      "ensureModuleImports": false
    }
  },
  "leases": {
    "framesBeforeAsking": 0,
    "framesWhileLoading": 1,
    "framesWithTwoLeases": 1,
    "framesEverOpened": 1,
    "askingAgainIsTheSameMermaid": true,
    "eachLeaseHasItsOwnMermaid": true,
    "mermaidImports": [
      "tests/dom/diagram-frame-mermaid-fixture.mjs"
    ],
    "frame": {
      "className": "metabrowser-diagram-frame",
      "sandbox": "allow-scripts allow-same-origin",
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
      "policyThenStylesheetThenScript": true,
      "policy": "default-src 'none'; script-src builtin_plugins/markdown/diagram-frame-entry.js tests/dom/; style-src builtin_plugins/markdown/diagram-frame.css 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'",
      "stylesheet": "builtin_plugins/markdown/diagram-frame.css",
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
      },
      {
        "render": "kpress-diagram-3",
        "text": "flowchart LR\n  A@{ img: \"https://example.com/a.png\" }",
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
    "hostsAfterFailing": 0,
    "imageShape": {
      "rejected": "Images in diagrams from untrusted text, such as a pull request's, are not loaded"
    }
  },
  "release": {
    "framesAfterOneRelease": 1,
    "releasedLeaseAsks": {
      "rejected": "The diagram frame's lease was released"
    },
    "releasedLeaseRenders": {
      "rejected": "The diagram frame's lease was released"
    },
    "framesAfterTheLast": 0,
    "renderInFlight": {
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
  "lost": {
    "removedInFlight": {
      "rejected": "The diagram frame closed"
    },
    "framesAfterRemoval": 0,
    "redrawn": {
      "resolved": [
        "svg"
      ]
    },
    "navigatedInFlight": {
      "rejected": "The diagram frame closed"
    },
    "framesAfterNavigating": 0,
    "redrawnAgain": {
      "resolved": [
        "svg"
      ]
    },
    "framesReopened": 2,
    "framesInPage": 0,
    "mermaidImports": 3,
    "newFramesGotTheConfiguration": [
      "neutral",
      "neutral",
      "neutral"
    ]
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
    "takenOutBeforeLoading": {
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
