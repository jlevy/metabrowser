---
cwd: ../..
sandbox: false
---
# Golden Test: Mermaid Diagrams in a Document

A fenced `mermaid` block in a Markdown document is drawn as a diagram, as GitHub draws
it. KPress marks each block as a figure with its source inside, and
`builtin_plugins/markdown/diagrams.js` draws the figures it finds: `drawDiagrams` in
`place-rendered.js` imports it only when a render has one, so a document without a
diagram asks for nothing.
A trusted render draws Mermaid’s SVG into the page.
An inert render, whose content security policy admits no inline style, draws each
diagram as an image of that SVG instead.

This browserless session runs the production modules with a stub Mermaid that draws a
labelled SVG and fails on demand.
The transcript pins these behaviors:

- The dialog’s view math: fit, zoom about a point, pan, reset, the scale bounds, the
  keys that act, the wheel and pinch, and the transform the stage takes.
- Mermaid’s configuration: strict security, no error diagram, and the theme the page
  shows.
- A render without a diagram returns no handle and loads no module.
- A trusted render loads the `mermaid` module once, draws the figures one at a time,
  shows a parse error with the source beside it, and gives each figure a copy button the
  shell owns, a source toggle, and an expand button.
- A theme change redraws every figure in the new theme, keeping the toggled state.
- The expanded dialog’s controls, keys, and close.
- Disposal, including disposal while a diagram is still drawing, leaves no listener.
- An over-long diagram and a failed module load show their error without drawing.
- An inert render draws an image whose source is the SVG as a `data:` address.
- A `.mmd` file’s Diagram view reads a truncated file whole and draws it as an image.

```console
$ node tests/dom/markdown-diagrams-session.js
{
  "view": {
    "steps": [
      {
        "action": "fit",
        "view": {
          "scale": 2,
          "x": 100,
          "y": 100
        }
      },
      {
        "action": "zoom-in",
        "view": {
          "scale": 2.5,
          "x": 0,
          "y": 50
        }
      },
      {
        "action": "zoom-in",
        "view": {
          "scale": 3.125,
          "x": -125,
          "y": -12.5
        }
      },
      {
        "action": "pan-left",
        "view": {
          "scale": 3.125,
          "x": -45,
          "y": -12.5
        }
      },
      {
        "action": "pan-up",
        "view": {
          "scale": 3.125,
          "x": -45,
          "y": 67.5
        }
      },
      {
        "action": "zoom-out",
        "view": {
          "scale": 2.5,
          "x": 64,
          "y": 114
        }
      },
      {
        "action": "pan-right",
        "view": {
          "scale": 2.5,
          "x": -16,
          "y": 114
        }
      },
      {
        "action": "pan-down",
        "view": {
          "scale": 2.5,
          "x": -16,
          "y": 34
        }
      },
      {
        "action": "reset",
        "view": {
          "scale": 2,
          "x": 100,
          "y": 100
        }
      }
    ],
    "bounds": {
      "most": 10,
      "least": 0.1
    },
    "largeDiagramFits": {
      "scale": 0.25,
      "x": 0,
      "y": 262.5
    },
    "keys": {
      "0": "reset",
      "+": "zoom-in",
      "=": "zoom-in",
      "-": "zoom-out",
      "_": "zoom-out",
      "ArrowUp": "pan-up",
      "ArrowLeft": "pan-left",
      "a": null
    },
    "keyWithCommand": null,
    "pinch": {
      "scale": 1.649,
      "x": -64.872,
      "y": -64.872
    },
    "scroll": {
      "scale": 1,
      "x": -30,
      "y": -40
    },
    "transform": "translate(-20px, 10px) scale(1.5)"
  },
  "config": {
    "light": {
      "startOnLoad": false,
      "securityLevel": "strict",
      "suppressErrorRendering": true,
      "theme": "default",
      "flowchart": {
        "diagramPadding": 48
      },
      "sequence": {
        "diagramMarginY": 40
      }
    },
    "dark": "dark"
  },
  "noDiagram": {
    "handle": null,
    "modulesAsked": []
  },
  "trusted": {
    "modulesAsked": [
      "mermaid"
    ],
    "whileTheFirstDraws": [
      "rendering",
      "source",
      "source"
    ],
    "figures": [
      {
        "status": "rendered",
        "drawing": "svg in default theme",
        "drawingShown": true,
        "sourceShown": false,
        "error": null
      },
      {
        "status": "error",
        "drawing": null,
        "drawingShown": null,
        "sourceShown": true,
        "error": "Parse error on line 2:"
      },
      {
        "status": "rendered",
        "drawing": "svg in default theme",
        "drawingShown": true,
        "sourceShown": false,
        "error": null
      }
    ],
    "renders": [
      "flowchart LR (page)",
      "sequenceDiagram (page)",
      "graph TD (page)"
    ],
    "themes": [
      "default",
      "default",
      "default"
    ],
    "toolbar": {
      "buttons": [
        "Copy diagram source",
        "Show source",
        "Expand diagram"
      ],
      "copies": "flowchart LR\n  A --> B",
      "copyIsOwned": true,
      "toggle": "Show source"
    }
  },
  "toggle": {
    "on": {
      "status": "rendered",
      "drawing": "svg in default theme",
      "drawingShown": false,
      "sourceShown": true,
      "error": null
    },
    "label": "Show diagram",
    "off": {
      "status": "rendered",
      "drawing": "svg in default theme",
      "drawingShown": true,
      "sourceShown": false,
      "error": null
    }
  },
  "themeChange": {
    "figures": [
      {
        "status": "rendered",
        "drawing": "svg in dark theme",
        "drawingShown": false,
        "sourceShown": true,
        "error": null
      },
      {
        "status": "error",
        "drawing": null,
        "drawingShown": null,
        "sourceShown": true,
        "error": "Parse error on line 2:"
      },
      {
        "status": "rendered",
        "drawing": "svg in dark theme",
        "drawingShown": true,
        "sourceShown": false,
        "error": null
      }
    ],
    "themes": [
      "default",
      "default",
      "default",
      "dark",
      "dark",
      "dark"
    ]
  },
  "dialog": {
    "open": true,
    "label": "Diagram",
    "controls": [
      "Zoom in",
      "Zoom out",
      "Reset view",
      "Pan up",
      "Pan down",
      "Pan left",
      "Pan right",
      "Close"
    ],
    "drawing": {
      "tag": "svg",
      "width": "400px",
      "maxWidth": "none"
    },
    "transforms": [
      "translate(100px, 100px) scale(2)",
      "translate(0px, 50px) scale(2.5)",
      "translate(100px, 100px) scale(2)",
      "translate(180px, 100px) scale(2)",
      "translate(231.898px, 100px) scale(3.297)",
      "translate(271.898px, 80px) scale(3.297)",
      "translate(100px, 100px) scale(2)"
    ],
    "pointerCaptured": [
      7
    ],
    "viewportFocused": true,
    "removedOnClose": true,
    "listenersLeft": 0
  },
  "escapeRemovesDialog": true,
  "dispose": {
    "dialogsLeft": 0,
    "rendersAfterDispose": 0,
    "themeListeners": 0,
    "figuresKept": [
      "rendered",
      "error",
      "rendered"
    ]
  },
  "disposeWhileDrawing": {
    "rendersStarted": 1,
    "figures": [
      "rendered",
      "source"
    ]
  },
  "tooLong": {
    "figure": {
      "status": "error",
      "drawing": null,
      "drawingShown": null,
      "sourceShown": true,
      "error": "This diagram's source is 50,009 characters; Mermaid draws at most 50,000."
    },
    "renders": 0
  },
  "loadFailure": [
    {
      "status": "error",
      "drawing": null,
      "drawingShown": null,
      "sourceShown": true,
      "error": "Mermaid could not load: Failed to fetch dynamically imported module"
    },
    {
      "status": "error",
      "drawing": null,
      "drawingShown": null,
      "sourceShown": true,
      "error": "Mermaid could not load: Failed to fetch dynamically imported module"
    }
  ],
  "inert": {
    "figure": {
      "status": "rendered",
      "drawing": "image",
      "drawingShown": true,
      "sourceShown": false,
      "error": null
    },
    "wrapsTheBlock": true,
    "imageAddress": "data:image/svg+xml;charset=utf-8",
    "imageSvg": "<svg id=\"metabrowser-mermaid-8\" viewBox=\"0 0 400 200\" data-theme=\"default\" width=\"400\" height=\"200\" xmlns=\"http://www.w3.org/2000/svg\"><g><text>flowchart LR</text></g></svg>",
    "render": [
      {
        "host": "measuring",
        "attached": true
      }
    ],
    "measuringHostsLeft": 0
  },
  "fileView": {
    "figure": {
      "status": "rendered",
      "drawing": "image",
      "drawingShown": true,
      "sourceShown": false,
      "error": null
    },
    "classes": "kpress-diagram kpress-mermaid metabrowser-diagram-file",
    "readWhole": [
      "flow.mmd"
    ],
    "drew": [
      "Whole --> File"
    ]
  },
  "listenersLeft": 0,
  "failures": []
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
