---
type: is
id: is-01m7kf0t56psry2ybyejpna2b4
title: "Chrome flake: tests/test_nav_reveal_chrome.py:217 'a long folder's fifth page by its address: the row is in view' fails with inView:false"
kind: bug
status: closed
priority: 1
version: 8
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-17T00:37:57.540Z
updated_at: 2026-11-18T05:36:29.709Z
started_at: 2026-11-18T04:30:44.246Z
closed_at: 2026-11-18T05:36:29.708Z
close_reason: "Fixed in PR #556: a landing's row scrolls once its folders open (app.js folderTravelAbove), and the Pulls list keeps a reveal's place while hidden (pulls-panel.js keptPlace); both checks strengthened to fail every run without the fixes."
resolution: null
duplicate_of: null
---
Seen on #453 at aeb95e38f (run 43982860238, test (3.14t)); docs-only change on main, did not recur at the next head. Reproduce under load (6x CPU throttle loop, as mb-alff and mb-nvo0 did) and fix the cause.

## Notes

2026-11-17: seen again on #490 at 8957c4d92 (run 44014847095, test (3.12)), same line 217 and inView:false (at [1251,1275,108,674,0]). The coordinator reran the failed jobs once per the known-flake rule. Second sighting, so raising to P1 for the fix pass.

2026-11-17 coordinator: not a 0.13 release gate (PR #497 lists it as a non-blocking follow-up); fix it in the fast-CI plan's Phase 3.

2026-11-17 (later): seen a third time on #516 at 10102ef6b (run 44175789894, test (3.13)), same case, row at y=1256 in a 674 px pane, inView false; #516 does not touch reveal or scrolling. Failed job rerun once per the known-flake rule. Also hit #504's stack-integration (test-chrome SHARD=2/4) earlier today.
2026-11-18 04:22 UTC: failed main at 5b1d2b055 (#525 merge), run 44235556541, chrome (3.12, 2/4): AssertionError phase list ending 'quick search: the file shown'. Second main failure (also dcf2bcfa8 on 2026-11-17). Rerun once per the known-flake rule; P1, fix now.
2026-11-18 05:40 UTC: fixed in PR #556 (branch claude/nav-reveal-flake, head 93fefc999). Two product causes. (1) The f905 check (five sightings): a landing's reveal opened the long folder with travel and scrolled in the same task, so scrollIntoView scrolled the row within the clipping 0 px .tree-children body, not the pane; once open, the row lay 7,433 px below a pane at scrollTop 0, on every landing. The test passed locally by reading during the travel, when the clipped row's box sat inside the pane; CI read late. revealWithin now scrolls once its folders' travel ends (folderTravelAbove, app.js); the driver's in-view read rejects a clipped row. (2) The main failure at 5b1d2b055 was a different check: step 10's Stack #286 never drawn after Files and back, list at 5733 px; its phase list ends at "stack walk", not "quick search: the file shown". The Pulls panel forgot a reveal's held place on hide, so stacks read after the first window regrouped #7 out of view; keptPlace now keeps it while hidden, and step 10 holds the stacks past the round trip. Before: each strengthened check failed 3 of 3 against the original code (as CI did); after: 20 of 20, and 10 of 10 at a 6x CPU throttle.
