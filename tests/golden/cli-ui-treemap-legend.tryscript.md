---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: the Treemap’s Legend and Its Shared Hover

The Treemap shows File Overview’s file-type legend under its tally bars, from the same
builder, and its cells, bars, and legend share one hover.
This session mounts the production Treemap view, its bars, and its legend on a folder of
three families with an ignored build folder, and prints each step’s legend, what is
marked as hovered, the cell under the pointer and whether it shimmers, the tooltip, and
what it is anchored on.
The map paints its cells on a canvas, which has no context here, so the cells it marks
and the cell under the pointer are read through `inspectTreemap`, and the pointer is a
mousemove on the viewport at a cell’s coordinates.
Each label shows its cell’s size only when the whole of it fits: in a pane 56 px wide
the folders leave their counts out and the files keep their sizes.
Pointing at a legend entry marks every cell of its family, the files of its type but no
nested folder, which is neutral, the family’s segment in every tally row that has one,
and the entry, with one tooltip: the counts of the family’s segment in the row the
legend’s shares are of, anchored on the entry.
Pointing at a cell marks the cell and its family’s entry and shows the cell’s own
tooltip, anchored on the hover anchor the map puts over the cell, which shimmers over a
file and not over a folder; moving within the cell, over its label, changes nothing.
The deepest cell under the pointer or a click is the one it takes: the build folder’s
frame, or the file inside it.
Pointing at a segment marks the segment and its family’s entry, and no cell.
The folder’s sums redrawing the bars under a cell or an entry keep the hover.
A layout under an entry draws its hover again on the new cells, and a layout under a
still pointer points at the cell now under it, on a new anchor: the same cell after a
resize, and another after the measure switches to Bytes.
The keys move the one focus proxy along the folder and file cells in layout order, Enter
opens the cell it is on, and Backspace opens the enclosing folder’s Treemap.
The view asks for the tree at the route’s largest node budget in the compact encoding,
and Show ignored turned off asks again for it without its ignored nodes.
Show ignored, a refreshed rollup, or the view’s disposal under the pointer puts the
hover away, and the browser’s entering the rebuilt entry brings it back.

```console
$ node tests/dom/treemap-legend-session.js
{
  "the legend under the tally bars, at rest": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
    "pointer": null,
    "shimmers": false,
    "tooltip": null,
    "anchoredOn": null
  },
  "each label at 800 px and at 56 px wide": {
    "wide": [
      "docs 800x600 5 files",
      "docs/a.md 234x385 100 B",
      "docs/b.md 234x385 100 B",
      "docs/build 327x302 1 file",
      "docs/build/d.py 323x280 300 B",
      "docs/c.py 469x193 300 B",
      "docs/e.json 327x276 50 B"
    ],
    "middle": [
      "docs 120x600 5 files",
      "docs/a.md 116x111 100 B",
      "docs/b.md 116x111 100 B",
      "docs/build 116x136 1 file",
      "docs/build/d.py 112x115 300 B",
      "docs/c.py 116x111 300 B",
      "docs/e.json 116x111 50 B"
    ],
    "narrow": [
      "docs 56x600 (no size)",
      "docs/a.md 52x110 100 B",
      "docs/b.md 52x110 100 B",
      "docs/build 52x139 (no size)",
      "docs/build/d.py 48x120 300 B",
      "docs/c.py 52x110 300 B",
      "docs/e.json 52x110 50 B"
    ]
  },
  "pointer on the Python entry, Show ignored on": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs/c.py",
      "cell docs/build/d.py"
    ],
    "pointer": null,
    "shimmers": false,
    "tooltip": "2 files · 600 B",
    "anchoredOn": "legend family:python"
  },
  "left the entry": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
    "pointer": null,
    "shimmers": false,
    "tooltip": null,
    "anchoredOn": null
  },
  "pointer on the c.py cell": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:python",
      "cell docs/c.py"
    ],
    "pointer": "cell docs/c.py",
    "shimmers": true,
    "tooltip": "docs/c.py / 300 B / modified 3y ago",
    "anchoredOn": "the anchor over docs/c.py"
  },
  "pointer moved within the c.py cell, over its label": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:python",
      "cell docs/c.py"
    ],
    "pointer": "cell docs/c.py",
    "shimmers": true,
    "tooltip": "docs/c.py / 300 B / modified 3y ago",
    "anchoredOn": "the anchor over docs/c.py"
  },
  "left the map": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
    "pointer": null,
    "shimmers": false,
    "tooltip": null,
    "anchoredOn": null
  },
  "pointer on the build folder's frame": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "cell docs/build"
    ],
    "pointer": "cell docs/build",
    "shimmers": false,
    "tooltip": "docs/build / 1 file · 300 B / gitignored",
    "anchoredOn": "the anchor over docs/build"
  },
  "pointer on the build folder's file": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:python",
      "cell docs/build/d.py"
    ],
    "pointer": "cell docs/build/d.py",
    "shimmers": true,
    "tooltip": "docs/build/d.py / 300 B / modified 3y ago / gitignored",
    "anchoredOn": "the anchor over docs/build/d.py"
  },
  "clicked the d.py cell, the build folder's frame, and the e.json cell": [
    [
      "docs/build/d.py"
    ],
    [
      "docs/build",
      "treemap"
    ],
    [
      "docs/e.json"
    ]
  ],
  "the folder's sums redrew the bars under the c.py cell": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:python",
      "cell docs/c.py"
    ],
    "pointer": "cell docs/c.py",
    "shimmers": true,
    "tooltip": "docs/c.py / 300 B / modified 3y ago",
    "anchoredOn": "the anchor over docs/c.py"
  },
  "the folder's sums redrew the bars under the Python entry": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs/c.py",
      "cell docs/build/d.py"
    ],
    "pointer": null,
    "shimmers": false,
    "tooltip": "2 files · 600 B",
    "anchoredOn": "legend family:python"
  },
  "pointer on the Total row's Markdown segment": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "Total family:markdown",
      "legend family:markdown"
    ],
    "pointer": null,
    "shimmers": false,
    "tooltip": "Documentation / Markdown / 2 files · 200 B",
    "anchoredOn": "Total family:markdown"
  },
  "the map laid out again under the Markdown entry": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "Files family:markdown",
      "Total family:markdown",
      "legend family:markdown",
      "cell docs/a.md",
      "cell docs/b.md"
    ],
    "pointer": null,
    "shimmers": false,
    "tooltip": "2 files · 200 B",
    "anchoredOn": "legend family:markdown"
  },
  "the map laid out again under a still pointer on the e.json cell": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:json",
      "cell docs/e.json"
    ],
    "pointer": "cell docs/e.json",
    "shimmers": true,
    "tooltip": "docs/e.json / 50 B / modified 3y ago",
    "anchoredOn": "the anchor over docs/e.json"
  },
  "the measure switched to Bytes under the still pointer": {
    "legend": "Python 70.6% Markdown 23.5% JSON 5.9%",
    "legendName": "Share of Total (850 B)",
    "marked": [
      "legend family:python",
      "cell docs/build/d.py"
    ],
    "pointer": "cell docs/build/d.py",
    "shimmers": true,
    "tooltip": "docs/build/d.py / 300 B / modified 3y ago / gitignored",
    "anchoredOn": "the anchor over docs/build/d.py"
  },
  "the measure switched back to Files under the still pointer": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:json",
      "cell docs/e.json"
    ],
    "pointer": "cell docs/e.json",
    "shimmers": true,
    "tooltip": "docs/e.json / 50 B / modified 3y ago",
    "anchoredOn": "the anchor over docs/e.json"
  },
  "the keyboard on the focus proxy": {
    "proxy": {
      "role": "button",
      "tabindex": "0",
      "hidden": false,
      "controls": 1
    },
    "focusOrder": [
      "docs/build",
      "docs/e.json",
      "docs/a.md",
      "docs/b.md",
      "docs/c.py",
      "docs/build/d.py"
    ],
    "keys": [
      {
        "key": "(none)",
        "on": "docs/build",
        "label": "build (folder, 1 file)"
      },
      {
        "key": "ArrowRight",
        "on": "docs/e.json",
        "label": "e.json (file, 50 B)"
      },
      {
        "key": "ArrowRight",
        "on": "docs/a.md",
        "label": "a.md (file, 100 B)"
      },
      {
        "key": "ArrowLeft",
        "on": "docs/e.json",
        "label": "e.json (file, 50 B)"
      },
      {
        "key": "ArrowLeft",
        "on": "docs/build",
        "label": "build (folder, 1 file)"
      },
      {
        "key": "Enter",
        "on": "docs/build",
        "label": "build (folder, 1 file)"
      },
      {
        "key": "Backspace",
        "on": "docs/build",
        "label": "build (folder, 1 file)"
      }
    ],
    "navigation": [
      [
        "docs/build",
        "treemap"
      ],
      [
        "",
        "treemap"
      ]
    ]
  },
  "Show ignored turned off under the Python entry": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [],
    "pointer": null,
    "shimmers": false,
    "tooltip": null,
    "anchoredOn": null,
    "asked": {
      "nodes": "max",
      "encoding": "compact",
      "ignored": "exclude"
    }
  },
  "pointer on the Python entry, Show ignored off": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs/c.py"
    ],
    "pointer": null,
    "shimmers": false,
    "tooltip": "1 file · 300 B",
    "anchoredOn": "legend family:python"
  },
  "the rollup refreshed under the pointer": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [],
    "pointer": null,
    "shimmers": false,
    "tooltip": null,
    "anchoredOn": null
  },
  "the browser entered the rebuilt entry": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs/c.py"
    ],
    "pointer": null,
    "shimmers": false,
    "tooltip": "1 file · 300 B",
    "anchoredOn": "legend family:python"
  },
  "the view disposed with the pointer on the e.json cell": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [],
    "pointer": null,
    "shimmers": false,
    "tooltip": null,
    "anchoredOn": null,
    "inspectable": false,
    "viewportListeners": 0
  }
}
? 0
```
