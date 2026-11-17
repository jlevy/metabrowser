---
type: is
id: is-01m7kf0t56psry2ybyejpna2b4
title: "Chrome flake: tests/test_nav_reveal_chrome.py:217 'a long folder's fifth page by its address: the row is in view' fails with inView:false"
kind: bug
status: open
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-17T00:37:57.540Z
updated_at: 2026-11-17T04:24:39.444Z
---
Seen on #453 at aeb95e38f (run 43982860238, test (3.14t)); docs-only change on main, did not recur at the next head. Reproduce under load (6x CPU throttle loop, as mb-alff and mb-nvo0 did) and fix the cause.

## Notes

2026-11-17: seen again on #490 at 8957c4d92 (run 44014847095, test (3.12)), same line 217 and inView:false (at [1251,1275,108,674,0]). The coordinator reran the failed jobs once per the known-flake rule. Second sighting, so raising to P1 for the fix pass.
