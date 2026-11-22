---
type: is
id: is-01m82c891g8pvraawchx4pwgvh
title: "Nightly soak 2026-11-20 (run 44737855133): tests/test_ref_selector_long_list_chrome.py:179 sees 6 rows, expects 1001, on main 21dc39da7"
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T19:38:12.910Z
updated_at: 2026-11-22T20:10:18.238Z
started_at: 2026-11-22T19:55:38.694Z
---
Nightly soak chrome (4, 3/4): assert 6 == 1001 at tests/test_ref_selector_long_list_chrome.py:179 (branch chooser long list, mb-dcp2). The chooser showed 6 branches instead of the full list once in five repetitions. Could be user-visible (truncated branch list). Find the mechanism before the 0.13.0 candidate.

## Notes

2026-11-22 investigation (worktree claude/soak-ref-selector, no code change, no PR): this failure is already fixed on main. Soak run 44737855133 ran main 21dc39da7; the failing assert was the 'middle' step, centerIndex 6 for expectedIndex 1001 (the list was back at its top, row 6 under its center; the list still held all 2001 branches, setSize 2001, so nothing was truncated). PR #658 (commit 7877276e8, merged 2026-11-20 17:04Z, about four hours after the soak) diagnosed this same run: renderNavFilterBar rebuilds the Files toolbar when a tally arrives, which takes the chooser out of the page and resets the list's scrollTop; the selector restored from drawnAt, set only by the scroll event, so a rebuild landing between a programmatic scroll and its scroll event left the list at its top. Fix: app.js reads the position before the rebuild and sets it after (holdScroll), keepScroll redraws for it. 7877276e8 is not an ancestor of 21dc39da7 and is an ancestor of the 11-21 and 11-22 soak heads (98c2dffd4, 48397f596), where this test passed in all repetitions (those runs failed on other tests: mb-oru2, time-limits). Checked 2026-11-22 on origin/main 2d52d2824: with the app.js keepScroll?.() call disabled the test fails with scrollThenToolbar got 0 want 20155, centerIndex 6 (the soak's signature); with it, the scroll assertions passed in 9 of 9 local runs at a load average near 260. Separate finding from those runs: 4 of 9 failed only on the last assert, openMs 6036 to 7694 ms against STEP_BOUND_MS 5000, at load average 230 to 290 on 10 cores (the bound was measured at load 17 to 35, opening 535 ms); not seen in CI or the soak. Suggest closing this bead as fixed by #658.
