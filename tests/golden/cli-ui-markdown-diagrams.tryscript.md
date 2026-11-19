---
cwd: ../..
sandbox: false
---
# Golden Test: Mermaid Diagrams in a Document

A fenced `mermaid` block in a Markdown document is drawn as a diagram, as GitHub draws
it. KPress draws it: its `js/diagrams.js` marks each block as a figure that holds its
source and draws the figures with a Mermaid the host supplies, and its opt-in
`js/diagram-controls.js` gives each figure a toolbar and a zoom and pan dialog.
KPress tests that drawing, the controls, their keys, and the view arithmetic itself.

This golden pins what Metabrowser decides around them: the host,
`builtin_plugins/markdown/diagrams.js`; `drawDiagrams` in `place-rendered.js`, which
imports the host only for a render that holds a diagram; and `mermaidFence` in
`mermaid-view.js`, the Markdown a `.mmd` file’s Diagram view renders.
The browserless session runs those production modules with KPress’s two modules as stubs
that `mb.ensureModule` returns, which record what they receive and draw nothing.
The transcript pins these behaviors:

- A render without a diagram returns no handle and asks for no module.
- A trusted render asks for both KPress modules, and for the `mermaid` module only when
  KPress calls the loader the host passes, and places its figures in the document.
- The theme KPress reads is the page’s resolved `data-theme`, and KPress redraws through
  `MetabrowserTheme`, or subscribes to nothing without it.
- Each copy button is the shell’s copy delegate for the figure’s source, marked as the
  page’s own, and each button’s label is the app’s tooltip in place of the browser’s
  `title`.
- `ready` settles after KPress’s, and disposing twice disposes KPress’s binding once and
  leaves the figures.
- An inert render’s `<pre lang="mermaid">` blocks become figures placed as images, and a
  block already inside a figure is not wrapped again.
- Only the mode `image` places as an image, the host’s own theme, subscription, and
  yield reach KPress unchanged, and `figures` fills once KPress has bound.
- Disposing before the KPress modules arrive binds nothing, and a handle disposed at
  once asks for nothing.
- A module that fails to load writes one warning and `ready` still settles; after
  disposal it writes none.
- A `.mmd` file’s text becomes one `mermaid` fence longer than any backtick run inside,
  and reads back whole, where a three-backtick fence would not for a line that is a
  fence.

How Mermaid lays out and paints a diagram is checked in headless Chrome by
`tests/test_markdown_diagrams_chrome.py`.

```console
$ node tests/dom/markdown-diagrams-session.js
{
  "noDiagram": {
    "handle": null,
    "modulesAsked": []
  },
  "trusted": {
    "modulesAsked": [
      "kpress-diagrams",
      "kpress-diagram-controls"
    ],
    "wrapped": 0,
    "options": [
      "controls",
      "mermaid",
      "placement",
      "subscribeTheme",
      "theme",
      "yieldBetween"
    ],
    "placement": "document",
    "yieldBetween": "not passed",
    "figuresBound": 2,
    "mermaidLoader": {
      "modulesAsked": [
        "mermaid"
      ],
      "returnsTheModule": true
    },
    "theme": {
      "dark": "dark",
      "light": "light",
      "sepia": "light",
      "(none)": "light"
    },
    "themeSubscription": {
      "listening": 1,
      "heard": [
        "redraw"
      ],
      "listeningAfterUnsubscribe": 0,
      "withoutRuntime": "function"
    },
    "controls": {
      "hostHooks": [
        "copy",
        "decorate"
      ],
      "handedToKpress": true,
      "copyButtons": [
        {
          "label": "Copy diagram source",
          "tooltip": "Copy diagram source",
          "title": null,
          "copy": "text",
          "copyText": "flowchart LR\n  A --> B",
          "copyLabel": "Copy diagram source",
          "ownedByThePage": true
        },
        {
          "label": "Copy diagram source",
          "tooltip": "Copy diagram source",
          "title": null,
          "copy": "text",
          "copyText": "sequenceDiagram\n  Alice->>Bob: Hi",
          "copyLabel": "Copy diagram source",
          "ownedByThePage": true
        }
      ],
      "delegatesOwned": 2
    },
    "readyBeforeKpress": false,
    "readyAfterKpress": true,
    "dispose": {
      "bindingDisposals": 1,
      "controlsDetached": 2,
      "figuresLeft": 2
    }
  },
  "inert": {
    "modulesAsked": [
      "kpress-diagrams",
      "kpress-diagram-controls"
    ],
    "placement": "image",
    "wrapped": [
      "pre lang=mermaid",
      "pre lang=mermaid"
    ],
    "eachInAFigure": true,
    "figuresBound": 2,
    "copyTexts": [
      "flowchart LR\n  A --> B",
      "graph TD\n  C --> D"
    ],
    "otherBlocksLeft": true
  },
  "blockInAFigure": {
    "wrapped": 0,
    "figuresBound": 1
  },
  "mountOptions": {
    "placementByMode": {
      "document": "document",
      "image": "image",
      "svg": "document",
      "(none)": "document"
    },
    "passedThrough": {
      "theme": true,
      "subscribeTheme": true,
      "yieldBetween": true
    },
    "figures": {
      "beforeBinding": 0,
      "afterReady": 2
    }
  },
  "decorateButton": {
    "labelled": {
      "tooltip": "Zoom in",
      "title": null
    },
    "unlabelled": {
      "tooltip": null,
      "title": null
    }
  },
  "copyWithoutOwnDelegate": {
    "label": "Copy diagram source",
    "tooltip": "Copy diagram source",
    "title": null,
    "copy": "text",
    "copyText": "graph A",
    "copyLabel": "Copy diagram source",
    "ownedByThePage": false
  },
  "disposeBeforeModules": {
    "modulesAsked": [
      "kpress-diagrams",
      "kpress-diagram-controls"
    ],
    "wrapped": 0,
    "bound": 0,
    "figures": 0,
    "warnings": []
  },
  "drawDisposedAtOnce": {
    "modulesAsked": [],
    "bound": 0
  },
  "loadFailure": {
    "modulesAsked": [
      "kpress-diagrams",
      "kpress-diagram-controls"
    ],
    "bound": 0,
    "ready": "settled",
    "warnings": [
      [
        "metabrowser markdown: the diagrams could not be drawn",
        "Failed to fetch dynamically imported module"
      ]
    ]
  },
  "loadFailureAfterDispose": {
    "warnings": []
  },
  "mermaidFence": [
    {
      "case": "plain",
      "markdown": "```mermaid\nflowchart LR\n  A --> B\n```\n",
      "roundTrips": true,
      "aThreeBacktickFenceWould": true
    },
    {
      "case": "ends in a newline",
      "markdown": "```mermaid\nflowchart LR\n  A --> B\n```\n",
      "roundTrips": true,
      "aThreeBacktickFenceWould": true
    },
    {
      "case": "a backtick label",
      "markdown": "```mermaid\nflowchart LR\n  A[\"`**bold**`\"] --> B\n```\n",
      "roundTrips": true,
      "aThreeBacktickFenceWould": true
    },
    {
      "case": "a line that is a fence",
      "markdown": "````mermaid\ngraph TD\n```\n  A --> B\n````\n",
      "roundTrips": true,
      "aThreeBacktickFenceWould": false
    },
    {
      "case": "a longer run inside",
      "markdown": "``````mermaid\ngraph TD\n  A[\"`````\"] --> B\n  C[\"```\"] --> D\n``````\n",
      "roundTrips": true,
      "aThreeBacktickFenceWould": true
    },
    {
      "case": "empty",
      "markdown": "```mermaid\n\n```\n",
      "roundTrips": true,
      "aThreeBacktickFenceWould": true
    }
  ],
  "warningsLeft": [],
  "failures": []
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
