---
type: is
id: is-01m7tbqzdjk3vty046954g84by
title: "Main red after #608: nav-collapse Chrome test says a press in Up does not land on Up"
kind: bug
status: closed
priority: 0
version: 5
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:55:23.307Z
updated_at: 2026-11-20T17:00:13.006Z
started_at: 2026-11-19T16:56:06.769Z
closed_at: 2026-11-19T17:18:13.290Z
close_reason: "PR #610 merged (test-only: wait for the committed view; sample layout after two frames)"
resolution: null
duplicate_of: null
---
Run 44492287878 on main 169496f05 (and #602's merge-up): tests/test_nav_collapse_chrome.py fails 'the chevron and Up are each a 24 px target, neither over the other, and a press anywhere in either lands on it' with owns {button:true, up:false}, up at left 328 right 352 top 4.5; chrome 3.12 4/4 and 3.14 3/4. Passed on #608's own CI. Introduced by #608 review-A A4 (mb-igva).

## Notes

PR #610 (branch claude/fix-main-nav-collapse, commit 4d15b3f8d), test-only. (1) test_nav_collapse_chrome 'owns.up false at load': timing race, not a product bug. The load phase waited for shellToolsReady and the shortcut hints, not for the folder view; the view is built in .preview-file-stage (inert, opacity 0, pointer-events none, app.js createFilePreviewStage) and committed later, so READ could find the staged copy of Up at its final box while a press there hit div.loading.mb-delayed-loading or the pane. Probe (20 navigations, headless Chrome, served folder): 16 had reads with tools ready and Up staged, 245 such reads, all missed (233 on the loading placeholder, 12 on the pane); 311 ready reads had no Up at all; every read after commit owned Up. Surfaced now because #608 review A added the press check; it passed #608's CI by chance. Fix: load waits for no stage and Up present; READ takes the committed Up; missed presses report what they hit. Local: unfixed failed 1 of 6; fixed 12 of 12 (6 parallel). (2) test_checkout_ref_selector_chrome 'branchLayout treeTops []': pre-existing race (sampler from mb-8ob8, nothing in #608 touches it; inference, not reproduced in 14 local runs incl. 4x CPU throttle). Sampler records the tree's first row on rAF; the switch waits on the DOM, which can hold rows before the new document's first frame. Measured locally: insertion-to-first-sampled-frame 0-58 ms, read 100-900 ms after. Fix: sampledLayout() reads after a double rAF. Fixed: 4 of 4 (parallel). Soak's time-limits failure was a GitHub API 502 in ci-report, unrelated.
