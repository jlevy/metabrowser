---
type: is
id: is-01m7kf0t56psry2ybyejpna2b4
title: "Chrome flake: tests/test_nav_reveal_chrome.py:217 'a long folder's fifth page by its address: the row is in view' fails with inView:false"
kind: bug
status: in_progress
priority: 1
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-17T00:37:57.540Z
updated_at: 2026-11-18T04:30:44.247Z
started_at: 2026-11-18T04:30:44.246Z
---
Seen on #453 at aeb95e38f (run 43982860238, test (3.14t)); docs-only change on main, did not recur at the next head. Reproduce under load (6x CPU throttle loop, as mb-alff and mb-nvo0 did) and fix the cause.

## Notes

2026-11-17: seen again on #490 at 8957c4d92 (run 44014847095, test (3.12)), same line 217 and inView:false (at [1251,1275,108,674,0]). The coordinator reran the failed jobs once per the known-flake rule. Second sighting, so raising to P1 for the fix pass.

2026-11-17 coordinator: not a 0.13 release gate (PR #497 lists it as a non-blocking follow-up); fix it in the fast-CI plan's Phase 3.

2026-11-17 (later): seen a third time on #516 at 10102ef6b (run 44175789894, test (3.13)), same case, row at y=1256 in a 674 px pane, inView false; #516 does not touch reveal or scrolling. Failed job rerun once per the known-flake rule. Also hit #504's stack-integration (test-chrome SHARD=2/4) earlier today.
2026-11-18 04:22 UTC: failed main at 5b1d2b055 (#525 merge), run 44235556541, chrome (3.12, 2/4): AssertionError phase list ending 'quick search: the file shown'. Second main failure (also dcf2bcfa8 on 2026-11-17). Rerun once per the known-flake rule; P1, fix now.
