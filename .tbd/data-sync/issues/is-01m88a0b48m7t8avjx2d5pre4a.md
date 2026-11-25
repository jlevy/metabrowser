---
type: is
id: is-01m88a0b48m7t8avjx2d5pre4a
title: "Docs draws a far file's whole Source body at load while its rendered view waits: #31's 17k-line book builds 72k nodes, 4 s of task"
kind: bug
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T02:54:22.342Z
updated_at: 2026-11-25T05:17:37.884Z
started_at: 2026-11-25T03:48:23.350Z
closed_at: 2026-11-25T05:17:37.879Z
close_reason: "Fixed in 38506a686 on PR #811: /pull/31 Docs loads in 0.57-0.61 s and 3.7k nodes, against 3.87-4.44 s and 72k at the base; numbers in the notes."
resolution: null
duplicate_of: null
---
Measured 2026-11-24 on finterm-ai/investment-research #31 (one new 876,516-byte, 17,177-line Markdown book among 13 files), headless Chrome 152 at 1,280 x 900, load average 270-330, two back-to-back pairs, origin/main runtime against claude/rendered-markdown-modes (PR #811): the Docs tab's load is unchanged by #811, 72,430-72,435 DOM nodes and 4.0-4.2 s of main-thread task in both builds, with long tasks totalling 0.65-1.31 s.

The nodes are the book's Source body: a file away from the first screen shows Source at once while its rendered view waits (diff-markdown.js, "a file away from the first screen shows Source at once" in tests/dom/diff-markdown-behavior.js), and Docs opens on Current, whose Source is the new file's lines in one column, so all 17k lines are drawn at load though the reader sees the rendered view when they reach it. #811 fixed the rendered draw on reaching the book (worst task 351 ms to 64 ms) but not this.

Candidates: draw a far rendered file's Source lazily (as the diff view's own fold materialization does, FOLD_MATERIALIZATION_BATCH_ROWS), or not at all until the reader nears it, keeping its estimated height; measure Docs and Changes load before and after.

## Notes

Fixed in 38506a686 on PR #811 (claude/rendered-markdown-modes). The hydration observer asks bodyWanted, so a held file whose rendered view hides its Source is not drawn; createMarkdownViews' onSource tells the diff when Source shows, and a file already reached is drawn then. Files on the first screen keep the FIRST_SCREEN_* hold. Test: heldSourceChecks in tests/dom/diff-view-behavior.js (a pending far file mounts a bounded node count).

Measured 2026-11-24 back to back against the origin/main runtime at :8476, headless Chrome 152 at 1,280 x 900, load average 185-190, rounds 9-11 at 6c16333 (product code of head 95302a9):
- /pull/31/docs: 0.57-0.61 s of main-thread task (base 3.87-4.44 s); 3,677-3,683 DOM nodes (base 72,461-72,471); layout 0.068-0.082 s (base 1.38-1.89 s); worst task none over 50 ms, 60 ms, 56 ms (base 124-264 ms).
- /pull/31/files: 0.49-0.54 s (base 0.48-0.58 s); 4,117 nodes (base 5,191); no task over 50 ms in either.
Rounds 6-8 at 38506a6 agreed: Docs 0.52-0.59 s and 2,968-3,641 nodes against 4.2-6.1 s and 72,430.

Limitation, as before this change: a file reached while its rendered view is still pending draws its Source in full when that view gives up; one cold-server run reaching the book took 5.66 s of task and 72,837 nodes. With the answer in, reaching it took 0.43 s and 21,409 nodes.
