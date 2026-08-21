---
type: is
id: is-01m0k603yscgjqhrw7zhar5rae
title: Nav row name, age, and size do not share a baseline
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-21T22:10:24.856Z
updated_at: 2026-08-21T22:10:24.856Z
---
The name, age, and size on a navigation row do not share a baseline. They are centered against each other instead, which is not the same thing once the font sizes differ.

`.tree-item` is `display: flex; align-items: center`. The name renders at 13px in a 19.5px line box; the age and size render at 12px in an 18px line box. Centering makes the two boxes concentric, so their tops differ by 0.75px — but a baseline sits at box top plus half-leading plus ascent, and ascent scales with font size, so concentric boxes put the baselines about half a pixel apart.

Measured on one file row in the running app:

    name   13px / 19.5px line box   text 251.25 - 269.75
    size   12px / 18px   line box   text 251.50 - 269.00
    age    12px / 18px   line box
    row    align-items: center

Half a pixel is why it reads as sloppy rather than as wrong: it lands differently at different zoom levels and device pixel ratios, so the row looks subtly unsettled rather than consistently offset.

Options, in the order they are worth trying:

- `align-items: baseline` for the text spans, keeping the icon in its own centered box. Baseline is the correct alignment for text of mixed sizes; the icon must not join it, because baseline-aligning a 16px square puts its bottom edge on the baseline.
- One line-height token shared by every span in the row, if the sizes are to stay different. This narrows the gap but does not close it, since ascent still scales with size.
- One font size for the whole row, distinguishing age and size by weight and color alone. This closes it exactly and is a design decision rather than a fix.

Check the same alignment in the two other places that build a row of this shape: the folder rollup rows and the git history rows. If they share the defect they should share the fix, and the row grammar belongs in the design system rather than in three stylesheets.
