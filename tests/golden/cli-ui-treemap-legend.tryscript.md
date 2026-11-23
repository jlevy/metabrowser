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
Pointing at a legend entry marks every cell of its family, the files of its type and the
folder it is the dominant type of, the family’s segment in every tally row that has one,
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
  "pointer on the Python entry, Show ignored on": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs",
      "cell docs/c.py",
      "cell docs/build",
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
    "tooltip": "docs/c.py / 1 file · 300 B / modified 2023-11-14",
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
    "tooltip": "docs/c.py / 1 file · 300 B / modified 2023-11-14",
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
      "legend family:python",
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
    "tooltip": "docs/build/d.py / 1 file · 300 B / modified 2023-11-14 / gitignored",
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
    "tooltip": "docs/c.py / 1 file · 300 B / modified 2023-11-14",
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
      "cell docs",
      "cell docs/c.py",
      "cell docs/build",
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
    "tooltip": "Markdown / 2 files · 200 B",
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
    "tooltip": "docs/e.json / 1 file · 50 B / modified 2023-11-14",
    "anchoredOn": "the anchor over docs/e.json"
  },
  "the measure switched to Bytes under the still pointer": {
    "legend": "Python 70.6% Markdown 23.5% JSON 5.9%",
    "legendName": "Share of Total (850 B)",
    "marked": [
      "legend family:markdown",
      "cell docs/a.md"
    ],
    "pointer": "cell docs/a.md",
    "shimmers": true,
    "tooltip": "docs/a.md / 1 file · 100 B / modified 2023-11-14",
    "anchoredOn": "the anchor over docs/a.md"
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
    "tooltip": "docs/e.json / 1 file · 50 B / modified 2023-11-14",
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
      "docs",
      "docs/a.md",
      "docs/b.md",
      "docs/c.py",
      "docs/e.json",
      "docs/build",
      "docs/build/d.py"
    ],
    "keys": [
      {
        "key": "(none)",
        "on": "docs",
        "label": "docs (folder, 5 files)"
      },
      {
        "key": "ArrowRight",
        "on": "docs/a.md",
        "label": "a.md (file, 100 B)"
      },
      {
        "key": "ArrowRight",
        "on": "docs/b.md",
        "label": "b.md (file, 100 B)"
      },
      {
        "key": "ArrowLeft",
        "on": "docs/a.md",
        "label": "a.md (file, 100 B)"
      },
      {
        "key": "ArrowRight",
        "on": "docs/b.md",
        "label": "b.md (file, 100 B)"
      },
      {
        "key": "Enter",
        "on": "docs/b.md",
        "label": "b.md (file, 100 B)"
      },
      {
        "key": "Backspace",
        "on": "docs/b.md",
        "label": "b.md (file, 100 B)"
      }
    ],
    "navigation": [
      [
        "docs/b.md"
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
    "anchoredOn": null
  },
  "pointer on the Python entry, Show ignored off": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs",
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
      "cell docs",
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
