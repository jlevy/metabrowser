---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Overview’s Compact Treemap

The production compact treemap under File Overview’s type breakdown asks for the
deepest, widest tree the server returns, shows a skeleton until the index has finished,
then draws every folder and file inside the map’s border.
The section’s legend hover marks the family’s cells, a cell opens its folder or file,
and a change of measure lays the map out again.
A refresh that fails keeps the map; a first rollup that fails, or an empty folder, takes
the map out of the section.
Disposal releases every listener, the watch, and the observer, and puts away only the
map’s own tooltip.

```console
$ node tests/dom/treemap-compact-session.js
{
  "steps": [
    {
      "step": "mounted, before any answer",
      "request": {
        "depth": 12,
        "top": 200,
        "ext_top": 0,
        "filename_top": 0,
        "remaining_top": 0
      },
      "hidden": false,
      "skeleton": true,
      "cells": []
    },
    {
      "step": "the index is still scanning",
      "hidden": false,
      "skeleton": true,
      "cells": []
    },
    {
      "step": "the index has finished",
      "insideBorder": true,
      "hidden": false,
      "skeleton": false,
      "cells": [
        "dir src/lib",
        "dir src/docs",
        "file src/README.md",
        "file src/lib/app.py",
        "file src/lib/util.py",
        "file src/lib/cli.py",
        "file src/docs/guide.md",
        "file src/docs/notes.md"
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
      "step": "activating a file cell and a folder cell",
      "navigation": [
        [
          {
            "path": "src/lib/app.py"
          }
        ],
        [
          {
            "path": "src/docs"
          }
        ]
      ]
    },
    {
      "step": "the measure switches to Files",
      "hidden": false,
      "skeleton": false,
      "cells": [
        "dir src/lib",
        "dir src/docs",
        "file src/README.md",
        "file src/lib/app.py",
        "file src/lib/util.py",
        "file src/lib/cli.py",
        "file src/docs/guide.md",
        "file src/docs/notes.md"
      ]
    },
    {
      "step": "a refresh fails after a complete answer",
      "hidden": false,
      "skeleton": false,
      "cells": [
        "dir src/lib",
        "dir src/docs",
        "file src/README.md",
        "file src/lib/app.py",
        "file src/lib/util.py",
        "file src/lib/cli.py",
        "file src/docs/guide.md",
        "file src/docs/notes.md"
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
      "step": "the first rollup fails",
      "hidden": true,
      "skeleton": false,
      "cells": []
    },
    {
      "step": "the folder is empty",
      "hidden": true,
      "skeleton": false,
      "cells": []
    }
  ],
  "warnings": [
    "Could not load the compact treemap.",
    "Could not load the compact treemap."
  ]
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
