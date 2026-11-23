---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Overview’s Compact Treemap

The production compact treemap under File Overview’s type breakdown follows the section
breakdown’s answers.
While the index scans it keeps its box with a skeleton and does not ask for the deep
tree; once the index has finished it asks for the deepest, widest tree the server
returns, the same request the Treemap view makes, and paints every folder and file
inside the map’s border, within an outer box for the folder itself.
The map paints on a canvas, which has no context here, so each step reads the layout,
the paint list, the labels, the focus proxy, and the hover anchor through
`inspectTreemap` and the elements the map keeps in the viewport.
The section’s legend hover marks the family’s cells.
The pointer, sent to the viewport at a cell’s coordinates, gives the cell under it an
anchor of its own that carries the tooltip and the shimmer, and the cell’s hover marks
it; moving on to another cell gives that one a new anchor, and leaving the map takes it
away. A click opens the Treemap view at the folder of the cell under it, and the outer
box opens it at the folder itself.
The arrow keys move the one focus proxy along the folder and file cells in layout order,
Enter opens the cell it is on, and Backspace, with no enclosing folder for the compact
map, is not taken. A change of measure or of Show ignored lays the map out again, and a
layout under a still pointer points at the cell now under it.
A refresh that fails keeps the map; a first rollup that fails shows that the map is
unavailable and recovers on Retry.
The box is left out when the breakdown failed, the index stopped at its cap before
finishing the folder, or the folder holds no files in the population shown.
Disposal with the pointer on a cell releases every listener, the watch, the observer,
and the cell’s hover, and puts away only the map’s own tooltip.

```console
$ node tests/dom/treemap-compact-session.js
{
  "steps": [
    {
      "step": "mounted, before the breakdown answers",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": false,
      "cells": [],
      "labelled": []
    },
    {
      "step": "the breakdown says the index is still scanning",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": false,
      "cells": [],
      "labelled": []
    },
    {
      "step": "the breakdown says the index has finished",
      "request": {
        "depth": "max",
        "top": "max",
        "ext_rank": "dual"
      },
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": true,
      "cells": [],
      "labelled": []
    },
    {
      "step": "the map's tree arrives",
      "insideBorder": true,
      "layers": [
        "canvas.tm-paint",
        "canvas.tm-marks",
        "div.tm-labels",
        "div.tm-focus",
        "div.tm-probes"
      ],
      "paint": {
        "rects": 13,
        "empty": 0,
        "dpr": 1
      },
      "focus": {
        "role": "button",
        "tabindex": "0",
        "hidden": false,
        "on": "src",
        "label": "src (folder, 27000 B)"
      },
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 600x218",
        "dir src/lib 257x189",
        "file src/cache.md 179x189",
        "dir src/docs 161x131",
        "file src/README.md 161x58",
        "file src/lib/app.py 138x163",
        "file src/lib/util.py 115x98",
        "file src/lib/cli.py 115x65",
        "file src/docs/guide.md 104x108",
        "file src/docs/notes.md 52x108"
      ],
      "labelled": [
        "src",
        "src/lib",
        "src/cache.md",
        "src/docs",
        "src/README.md",
        "src/lib/app.py",
        "src/lib/util.py",
        "src/lib/cli.py",
        "src/docs/guide.md",
        "src/docs/notes.md"
      ]
    },
    {
      "step": "pointing at the Python legend entry",
      "marked": [
        "src/lib/app.py",
        "src/lib/util.py",
        "src/lib/cli.py"
      ],
      "markOps": [
        "copy src/lib/app.py",
        "copy src/lib/util.py",
        "copy src/lib/cli.py"
      ]
    },
    {
      "step": "the pointer on the app.py cell",
      "pointer": {
        "on": "src/lib/app.py",
        "anchor": "tm-cell tm-hover-anchor tm-file",
        "shimmers": true,
        "tooltip": "src/lib/app.py / 1 files · 6000 B / modified then",
        "marked": [
          "src/lib/app.py"
        ],
        "cursor": "pointer"
      }
    },
    {
      "step": "the pointer moves on to the README.md cell",
      "pointer": {
        "on": "src/README.md",
        "anchor": "tm-cell tm-hover-anchor tm-file",
        "shimmers": true,
        "tooltip": "src/README.md / 1 files · 2500 B / modified then",
        "marked": [
          "src/README.md"
        ],
        "cursor": "pointer"
      }
    },
    {
      "step": "the pointer leaves the map",
      "pointer": {
        "on": null,
        "anchor": null,
        "cursor": ""
      }
    },
    {
      "step": "clicking two file cells and a folder cell opens the Treemap at their folders",
      "navigation": [
        [
          {
            "path": "src/lib"
          },
          {
            "viewId": "treemap"
          }
        ],
        [
          {
            "path": "src/docs"
          },
          {
            "viewId": "treemap"
          }
        ],
        [
          {
            "path": "src"
          },
          {
            "viewId": "treemap"
          }
        ]
      ]
    },
    {
      "step": "clicking the outer box opens the Treemap at the folder",
      "outerBox": "labelled, around the tree",
      "navigation": [
        [
          {
            "path": "src"
          },
          {
            "viewId": "treemap"
          }
        ]
      ]
    },
    {
      "step": "the keyboard",
      "focusOrder": [
        "src",
        "src/lib",
        "src/cache.md",
        "src/docs",
        "src/README.md",
        "src/lib/app.py",
        "src/lib/util.py",
        "src/lib/cli.py",
        "src/docs/guide.md",
        "src/docs/notes.md"
      ],
      "keys": [
        "ArrowRight -> lib (folder, 11000 B)",
        "ArrowRight -> cache.md (file, 9000 B)",
        "ArrowLeft -> lib (folder, 11000 B)"
      ],
      "enter": {
        "taken": true,
        "navigation": [
          [
            {
              "path": "src/lib"
            },
            {
              "viewId": "treemap"
            }
          ]
        ]
      },
      "backspace": {
        "taken": false
      }
    },
    {
      "step": "the measure switches to Files under a still pointer",
      "pointerBefore": {
        "on": "src/cache.md",
        "anchor": "tm-cell tm-hover-anchor tm-file",
        "shimmers": true,
        "tooltip": "src/cache.md / 1 files · 9000 B / modified then / gitignored",
        "marked": [
          "src/cache.md"
        ],
        "cursor": "pointer"
      },
      "pointerAfter": {
        "on": "src/docs/guide.md",
        "anchor": "tm-cell tm-hover-anchor tm-file",
        "shimmers": true,
        "tooltip": "src/docs/guide.md / 1 files · 3000 B / modified then",
        "marked": [
          "src/docs/guide.md"
        ],
        "cursor": "pointer"
      },
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 600x218",
        "dir src/lib 266x189",
        "dir src/docs 178x189",
        "file src/README.md 151x94",
        "file src/cache.md 151x95",
        "file src/lib/app.py 87x163",
        "file src/lib/cli.py 87x163",
        "file src/lib/util.py 87x163",
        "file src/docs/guide.md 87x164",
        "file src/docs/notes.md 87x164"
      ],
      "labelled": [
        "src",
        "src/lib",
        "src/docs",
        "src/README.md",
        "src/cache.md",
        "src/lib/app.py",
        "src/lib/cli.py",
        "src/lib/util.py",
        "src/docs/guide.md",
        "src/docs/notes.md"
      ]
    },
    {
      "step": "Show ignored is turned off",
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 600x218",
        "dir src/lib 305x189",
        "dir src/docs 204x189",
        "file src/README.md 87x189",
        "file src/lib/app.py 100x163",
        "file src/lib/cli.py 100x163",
        "file src/lib/util.py 100x163",
        "file src/docs/guide.md 100x164",
        "file src/docs/notes.md 100x164"
      ],
      "labelled": [
        "src",
        "src/lib",
        "src/docs",
        "src/README.md",
        "src/lib/app.py",
        "src/lib/cli.py",
        "src/lib/util.py",
        "src/docs/guide.md",
        "src/docs/notes.md"
      ]
    },
    {
      "step": "the tab is shown again after a change while hidden",
      "refreshes": 1
    },
    {
      "step": "a refresh fails after a complete answer",
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 600x218",
        "dir src/lib 305x189",
        "dir src/docs 204x189",
        "file src/README.md 87x189",
        "file src/lib/app.py 100x163",
        "file src/lib/cli.py 100x163",
        "file src/lib/util.py 100x163",
        "file src/docs/guide.md 100x164",
        "file src/docs/notes.md 100x164"
      ],
      "labelled": [
        "src",
        "src/lib",
        "src/docs",
        "src/README.md",
        "src/lib/app.py",
        "src/lib/cli.py",
        "src/lib/util.py",
        "src/docs/guide.md",
        "src/docs/notes.md"
      ]
    },
    {
      "step": "disposed with the pointer on a cell",
      "viewportListeners": [],
      "controlListeners": 0,
      "activeListeners": 0,
      "watchDisposed": true,
      "observerDisconnected": true,
      "hoverReleased": true,
      "inspectable": false,
      "tooltipHides": 1,
      "hidOwnTooltipOnly": true
    },
    {
      "step": "the breakdown's request fails",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": [],
      "labelled": []
    },
    {
      "step": "Retry: the breakdown answers, and the map follows",
      "hidden": false,
      "drawn": true
    },
    {
      "step": "the map's first rollup fails",
      "hidden": false,
      "skeleton": false,
      "unavailable": true,
      "asked": true,
      "cells": [],
      "labelled": []
    },
    {
      "step": "Retry: the map asks again, and its tree arrives",
      "refreshes": 1,
      "hidden": false,
      "drawn": true
    },
    {
      "step": "the index stopped at its cap mid-folder",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": [],
      "labelled": []
    },
    {
      "step": "the folder is empty",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": [],
      "labelled": []
    },
    {
      "step": "every file is ignored, and Show ignored is off",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": [],
      "labelled": []
    },
    {
      "step": "Show ignored is turned on",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": true,
      "cells": [],
      "labelled": []
    },
    {
      "step": "the box is too narrow to draw in",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": true,
      "cells": [],
      "labelled": []
    },
    {
      "step": "the pane widens",
      "hidden": false,
      "drawn": true
    }
  ],
  "warnings": [
    "Could not load the compact treemap.",
    "Could not load the compact treemap."
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
