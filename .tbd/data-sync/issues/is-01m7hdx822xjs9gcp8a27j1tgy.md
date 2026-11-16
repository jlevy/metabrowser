---
type: is
id: is-01m7hdx822xjs9gcp8a27j1tgy
title: "PR #467 A1 follow-up: pin the header session's stack-chip width and cut so a chip change fails visibly"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T05:40:03.264Z
updated_at: 2026-11-16T06:16:59.857Z
---
Review A (https://github.com/jlevy/metabrowser/pull/467#pullrequestreview-5915424529), Design Assessment: the figures in docs/design-system.md (Native stack navigation paragraph: one stack 54.75 px; two named stacks 156.31 px; cuts 77.69 px at 560 px and 80.85 px at 360 px) are prose nothing checks; nothing failed when #463 widened the chip. tests/dom/github-pull-header-chrome.mjs computes chipMoves.chipWidth and chipMoves.cut but only checks relations (nothing moves, chip whole, 8 px clear). Not done in PR #467 because an absolute pixel pin is not a small change: these are text-advance widths in the KPress faces measured on macOS Chrome 152, and Linux CI Chrome may round glyph advances differently, so a pin needs a CI measurement and a tolerance chosen from it (AGENTS.md 'Measure before bounding'), or a golden that prints the figures per platform. Options: (a) a check with a tolerance measured on both runners; (b) have the session print the figures and have a test compare them to the doc's numbers on one named platform.
