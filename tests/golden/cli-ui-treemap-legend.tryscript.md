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
marked as hovered, the tooltip, and what it is anchored on.
Pointing at a legend entry marks every cell of its family, the files of its type and the
folder it is the dominant type of, the family’s segment in every tally row that has one,
and the entry, with one tooltip: the counts of the family’s segment in the row the
legend’s shares are of, anchored on the entry.
Pointing at a cell marks the cell and its family’s entry and shows the cell’s own
tooltip, and crossing the cell’s own label does not leave it.
Pointing at a segment marks the segment and its family’s entry, and no cell.
A layout under an entry draws its hover again on the new cells, and a layout under a
cell lets go of the cell’s hover until the browser enters the new cell.
Show ignored, a refreshed rollup, or the view’s disposal under the pointer puts the
hover away, and the browser’s entering the rebuilt entry brings it back.

```console
$ node tests/dom/treemap-legend-session.js
{
  "the legend under the tally bars, at rest": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
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
      "cell docs/c.py",
      "cell docs/build",
      "cell docs/build/d.py"
    ],
    "tooltip": "2 files · 600 B",
    "anchoredOn": "legend family:python"
  },
  "left the entry": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
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
    "tooltip": "docs/c.py / 1 file · 300 B / modified 2023-11-14",
    "anchoredOn": "cell docs/c.py"
  },
  "pointer across the c.py cell's own label": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:python",
      "cell docs/c.py"
    ],
    "tooltip": null,
    "anchoredOn": null
  },
  "left the cell": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
    "tooltip": null,
    "anchoredOn": null
  },
  "pointer on the build folder": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:python",
      "cell docs/build"
    ],
    "tooltip": "docs/build / 1 file · 300 B / gitignored",
    "anchoredOn": "cell docs/build"
  },
  "pointer on the Total row's Markdown segment": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "Total family:markdown",
      "legend family:markdown"
    ],
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
    "tooltip": "2 files · 200 B",
    "anchoredOn": "legend family:markdown"
  },
  "the map laid out again under the e.json cell": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [],
    "tooltip": "docs/e.json / 1 file · 50 B / modified 2023-11-14",
    "anchoredOn": "cell docs/e.json"
  },
  "the browser entered the redrawn e.json cell": {
    "legend": "Markdown 40% Python 40% JSON 20%",
    "legendName": "Share of Total (5 files)",
    "marked": [
      "legend family:json",
      "cell docs/e.json"
    ],
    "tooltip": "docs/e.json / 1 file · 50 B / modified 2023-11-14",
    "anchoredOn": "cell docs/e.json"
  },
  "Show ignored turned off under the Python entry": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [],
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
      "cell docs/c.py"
    ],
    "tooltip": "1 file · 300 B",
    "anchoredOn": "legend family:python"
  },
  "the rollup refreshed under the pointer": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [],
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
    "tooltip": "1 file · 300 B",
    "anchoredOn": "legend family:python"
  },
  "the view disposed under the pointer": {
    "legend": "Markdown 50% JSON 25% Python 25%",
    "legendName": "Share of Files (4 files)",
    "marked": [],
    "tooltip": null,
    "anchoredOn": null
  }
}
? 0
```
