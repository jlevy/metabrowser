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
returns, the same request the Treemap view makes, and draws every folder and file inside
the map’s border, within an outer box for the folder itself.
The section’s legend hover marks the family’s cells, a cell opens the Treemap view at
its folder, the outer box opens it at the folder itself, and a change of measure or of
Show ignored lays the map out again.
A refresh that fails keeps the map; a first rollup that fails shows that the map is
unavailable and recovers on Retry.
The box is left out when the breakdown failed, the index stopped at its cap before
finishing the folder, or the folder holds no files in the population shown.
Disposal releases every listener, the watch, and the observer, and puts away only the
map’s own tooltip.

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
      "cells": []
    },
    {
      "step": "the breakdown says the index is still scanning",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": false,
      "cells": []
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
      "cells": []
    },
    {
      "step": "the map's tree arrives",
      "insideBorder": true,
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 599x217",
        "dir src/lib 242x188",
        "file src/cache.md 198x188",
        "dir src/docs 154x121",
        "file src/README.md 154x67",
        "file src/lib/app.py 129x162",
        "file src/lib/util.py 108x97",
        "file src/lib/cli.py 108x64",
        "file src/docs/guide.md 99x98",
        "file src/docs/notes.md 49x98"
      ]
    },
    {
      "step": "pointing at the Python legend entry",
      "marked": [
        "src/lib",
        "src/lib/app.py",
        "src/lib/util.py",
        "src/lib/cli.py"
      ]
    },
    {
      "step": "activating two file cells and a folder cell opens the Treemap at their folders",
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
      "step": "activating the outer box opens the Treemap at the folder",
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
      "step": "the measure switches to Files",
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 599x217",
        "dir src/lib 254x188",
        "dir src/docs 169x188",
        "file src/README.md 169x94",
        "file src/cache.md 169x94",
        "file src/lib/app.py 83x162",
        "file src/lib/util.py 83x162",
        "file src/lib/cli.py 83x162",
        "file src/docs/guide.md 82x164",
        "file src/docs/notes.md 82x164"
      ]
    },
    {
      "step": "Show ignored is turned off",
      "hidden": false,
      "skeleton": false,
      "unavailable": false,
      "asked": true,
      "cells": [
        "dir src 599x217",
        "dir src/lib 297x188",
        "dir src/docs 198x188",
        "file src/README.md 98x188",
        "file src/lib/app.py 97x162",
        "file src/lib/util.py 97x162",
        "file src/lib/cli.py 97x162",
        "file src/docs/guide.md 96x163",
        "file src/docs/notes.md 96x163"
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
        "dir src 599x217",
        "dir src/lib 297x188",
        "dir src/docs 198x188",
        "file src/README.md 98x188",
        "file src/lib/app.py 97x162",
        "file src/lib/util.py 97x162",
        "file src/lib/cli.py 97x162",
        "file src/docs/guide.md 96x163",
        "file src/docs/notes.md 96x163"
      ]
    },
    {
      "step": "disposed",
      "viewportListeners": [],
      "controlListeners": 0,
      "activeListeners": 0,
      "watchDisposed": true,
      "observerDisconnected": true,
      "tooltipHides": 1,
      "hidOwnTooltipOnly": true
    },
    {
      "step": "the breakdown's request fails",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": []
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
      "cells": []
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
      "cells": []
    },
    {
      "step": "the folder is empty",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": []
    },
    {
      "step": "every file is ignored, and Show ignored is off",
      "hidden": true,
      "skeleton": false,
      "unavailable": false,
      "asked": false,
      "cells": []
    },
    {
      "step": "Show ignored is turned on",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": true,
      "cells": []
    },
    {
      "step": "the box is too narrow to draw in",
      "hidden": false,
      "skeleton": true,
      "unavailable": false,
      "asked": true,
      "cells": []
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
