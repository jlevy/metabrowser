---
type: is
id: is-01m7hdz8vrx2wktnbpnskn2qd5
title: "PR #464 A3: a reveal draws only one more page of a long folder"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:09.623Z
updated_at: 2026-11-16T06:21:48.080Z
started_at: 2026-11-16T05:41:17.085Z
---
Medium. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). app.js:9113,9147,9170-9181: mountTreePageHolding mounts one TREE_PAGE_SIZE page; rows past 400 stay undrawn. Loop, production-like stand-in, Chrome fixture past 400 files, measure cost for thousands.

## Notes

Escalated to the coordinator 2026-11-15 (brief: stop and report if over 100 ms). With the loop in revealWithin (while !row && mountTreePageHolding), headless Chrome on live metab servers, load avg 14-21, revealFileRow of a long folder's last file with its first page drawn: one page (row 300) 13-19 ms; 2000 files 204 ms median; 5000 files 370-826 ms (median 783); 10000 files 2.75 s. Profile at 5000: scrollIntoView forced layout 165 ms, mountNextTreePage 182 ms over 24 pages (renderTreeNodes 33, applyTreeFilters 61). With applyTreeFilters run once after the loop: 5000 -> 310 ms, 10000 -> 677 ms (layout 164 / 335 ms). Drawing every row before the target exceeds 100 ms past about 2000 rows whatever the batching. Loop not committed; data in attic/a3-measure/results.json of the reveal-on-navigate worktree. Options: draw only the page holding the row behind a 'more' row of its own; or accept the loop's cost; or a measured cap with the file named as not drawn.
