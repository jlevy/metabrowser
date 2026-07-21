# Research: Folder Treemap Layout and Prior Art

**Date:** 2026-07-20 (last updated 2026-07-20)

**Author:** Metabrowser maintainers

**Status:** Complete

## Overview

Validation notes for the rendering decisions in the
[folder views and treemap overview plan](../specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md):
a survey of how established disk-usage visualizers handle layout and scanning, plus
measured results from the layout spike that shipped as
`builtin_plugins/folder/treemap_layout.js`.

## Prior Art

Conventions shared across WinDirStat, KDirStat, SequoiaView, GrandPerspective,
SpaceSniffer, TreeSize, Baobab, and WizTree, and the terminal tools ncdu, dust, dua, and
gdu:

- **Squarified layout is the default.** Every GUI tool uses the Bruls, Huizing, and van
  Wijk row-packing algorithm or a close variant; slice-and-dice appears only as an
  option (KDirStat) because thin slivers are unreadable.
  SequoiaView’s contribution is cushion shading, a rendering effect orthogonal to the
  layout; SpaceSniffer animates the same rectangle model.
- **Scan-while-render.** SpaceSniffer and WizTree draw during the scan and refine as
  directories complete; WizTree’s speed comes from reading the NTFS MFT instead of
  walking — the analog here is reading the already-built `InventoryIndex` instead of a
  second crawl.
- **Small items aggregate.** Every tool stops subdividing around a few pixels;
  WinDirStat merges the tail into gray filler regions rather than dropping bytes
  silently. Terminal tools cap list length the same way.
- **Color encodes one dimension at a time.** WinDirStat and GrandPerspective color by
  file type; DaisyDisk by depth ring; none mix encodings in one view.
  Metabrowser colors by file type by default with age as the alternative, and always
  shows the tree column’s colored age label beside cell names, so the second dimension
  rides as text rather than a second fill encoding.
- **Zoom is re-rooting.** Double-click (WinDirStat) or click (DaisyDisk, Baobab)
  re-roots the visualization at the chosen directory with a breadcrumb or up control to
  return — the same model as “zoom is navigation” in the plan.

## Spike Results

Measured in `tests/dom/treemap_layout_behavior.js` (Node vm, this container):

- `layoutTree` emits **800 cells in ~3 ms** against the 16 ms budget, including
  squarify, two-level nesting, culling, and remainder synthesis.
- Aspect quality holds under 8:1 for representative mixes; area is conserved within
  rounding across the emitted set.
- `InventoryIndex.rollup` computes a 40k-entry synthetic subtree in well under the 150
  ms budget (`tests/test_browser_rollup.py` prints the measured value; the live
  6.8k-file repository answers in single-digit milliseconds).

Layout throughput is not the binding constraint; DOM node count is.
The `maxCells` cap (800) and minimum cell size govern perceived density, matching the
prior-art convention of aggregating the tail.

## Confirmed Decisions

- Hand-rolled squarify in plain DOM (spec decision 6) is sufficient: the algorithm is
  ~130 lines, no vendored library is needed, and labels stay selectable text.
- `dominant_ext` coloring for directory cells in type mode is readable when the
  directory is homogeneous and neutral otherwise; kept, with the tooltip carrying the
  exact breakdown.
- Nested directory cells intercept clicks over their area, so the parent’s activation
  target is its label strip — the WinDirStat behavior, made explicit: the strip is the
  button (no nested interactive ancestors) and keyboard users reach the parent in layout
  order regardless.

## References

- Bruls, Huizing, van Wijk, “Squarified Treemaps” (Eurographics/TCVG 2000)
- [Folder views and treemap overview plan](../specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
