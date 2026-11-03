---
type: is
id: is-01m6fczffs8pdsdktnahd1ked2
title: Mount a very large comparison's file list without one long task
kind: task
status: open
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-03T00:29:37.144Z
updated_at: 2026-11-03T07:26:17.492Z
---
Measured on the large-PR performance layer: the mount is a single task of 262-275 ms at 44k nodes and 616-628 ms at 115k, against a proposed 200 ms; github.com took 390. A content-visibility probe did not move it (625 vs 626, 257 vs 266), so it needs batched mounting or a window, designed together with the pull-request nav. Deferred-file lines at 115k nodes (122-214 ms against 150) and the queue on a +442k-line case (813 ms against 300) are the two other open budget misses.

## Notes

MAX_MANIFEST_FILES is 2,000, under GitHub's 3,000: a pull request of 2,001 to 3,000 files shows a cut list in Files changed (listTruncated) and the Pulls tab falls back to GitHub's list. Raise it only together with batched mounting, after measuring the mount at 3,000 files.


2026-11-03: review E on PR 284 measured the mount at 1,031 files as one rendering task of 1.0 to 1.2 s (style 152, layout 474, commit 387 ms; 114,609 nodes), with Back at 0.9 to 1.3 s and the Conversation click at 0.9 to 1.3 s; content-visibility and static bars did not move it. The fix, drawing the first screen and hydrating the rest through the deferred path, is being built on PR 284.


2026-11-03, E1 landed on PR 284 in 9b624b3a (mb-vy01). Design: mountDiffView measures the pane and a bar and a row (two probe files in the layout it already forces for the width), draws rows only for ready files whose estimated top is within the pane and one screen more (firstScreenBudget), and holds every later ready file with its answer in the deferred path: reserved rows from patchRows, drawn one a frame when reached or jumped to, never requested, counted as loaded; a jumped-to held file gets one frame for its bar before its rows. Measured in visible Chrome 152, adjacent pairs against 9d6e0930, alternating order, astral-sh/ruff #29817 (1,031 files): first line 969-1,548 vs 1,565-2,343 ms and longest task 136-330 vs 653-1,182 ms, 23,451 vs 114,609 nodes (7 pairs, load 9-15); Back 432-461 vs 1,410-1,520 ms, longest task 311-325 (3 pairs, load 19-29); Conversation click 449-457 vs 947-962 ms, no request after the click (3 pairs, load 30-48). #29121 (1,627): first line 1,503-1,785 vs 1,702-3,410, longest task 175-180 vs 318-585 (5 pairs, load 7-37); Back 608-613 vs 860-866, task 433-446; click 400-407 vs 591-605. python/typeshed #15711 (650): first line 912-1,102 vs 999-1,117, task 166-169 vs 241-243 (load 29-41); Back 137-149 vs 173-178; click 165-281 vs 175-351. #29869 (39): first line 831-956 vs 1,276-1,353, no task over 50 ms vs 379-393 (load 25-38); Back 35-36 vs 503-514; click 48-56 vs 349-474. Jumps at 1,031: deferred lines 61-89 vs 118-157 ms, held-file bar 17-25 and lines 39-72, drift 0, held key 33 ms a step. Against signed-out github.com at 1,031 files, 6 adjacent pairs at load 8-12: first line 910-1,176 vs 719-1,763 ms, faster in 2 and slower in 4 (1.19x-1.27x); the cold manifest (452-531 ms of the first request, E3, mb-ph3m) is now the largest part. github.com pairs at 650, 39 and 1,627 ran at load 11-400 and are not usable. What is still open here: the remaining rendering task is not the bars' offscreen layout or paint. Traces of the new build at load 9-16 give a 306-333 ms rendering task of layout 79-127 (style 44-50 when split out), pre-paint 18-23 and commit 155-166, with 12 composited layers; content-visibility:auto on .diff-file with an intrinsic size, static bars, and no reserved heights (CSS-only diagnostics, one trace each in two rounds) left it at 311/333, 306/309 and 321/327 ms, and later pairs at load 8-12 showed the same build at 114-158 ms, so commit time varies with the machine's compositor load. Next step: trace the 1,031-file rendering task at a quiet load with the drawn rows and the bars hidden in turn (scratch traces2.sh), and decide the window over the bars with the nav (mb-q3jt); then E3, which is the critical path for "faster than github.com" at 1,031 files.
