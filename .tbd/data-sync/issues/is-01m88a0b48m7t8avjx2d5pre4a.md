---
type: is
id: is-01m88a0b48m7t8avjx2d5pre4a
title: "Docs draws a far file's whole Source body at load while its rendered view waits: #31's 17k-line book builds 72k nodes, 4 s of task"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T02:54:22.342Z
updated_at: 2026-11-25T03:48:23.352Z
started_at: 2026-11-25T03:48:23.350Z
---
Measured 2026-11-24 on finterm-ai/investment-research #31 (one new 876,516-byte, 17,177-line Markdown book among 13 files), headless Chrome 152 at 1,280 x 900, load average 270-330, two back-to-back pairs, origin/main runtime against claude/rendered-markdown-modes (PR #811): the Docs tab's load is unchanged by #811, 72,430-72,435 DOM nodes and 4.0-4.2 s of main-thread task in both builds, with long tasks totalling 0.65-1.31 s.

The nodes are the book's Source body: a file away from the first screen shows Source at once while its rendered view waits (diff-markdown.js, "a file away from the first screen shows Source at once" in tests/dom/diff-markdown-behavior.js), and Docs opens on Current, whose Source is the new file's lines in one column, so all 17k lines are drawn at load though the reader sees the rendered view when they reach it. #811 fixed the rendered draw on reaching the book (worst task 351 ms to 64 ms) but not this.

Candidates: draw a far rendered file's Source lazily (as the diff view's own fold materialization does, FOLD_MATERIALIZATION_BATCH_ROWS), or not at all until the reader nears it, keeping its estimated height; measure Docs and Changes load before and after.
