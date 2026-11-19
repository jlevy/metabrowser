---
type: is
id: is-01m7tbqzdjk3vty046954g84by
title: "Main red after #608: nav-collapse Chrome test says a press in Up does not land on Up"
kind: bug
status: in_progress
priority: 0
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:55:23.307Z
updated_at: 2026-11-19T16:56:06.770Z
started_at: 2026-11-19T16:56:06.769Z
---
Run 44492287878 on main 169496f05 (and #602's merge-up): tests/test_nav_collapse_chrome.py fails 'the chevron and Up are each a 24 px target, neither over the other, and a press anywhere in either lands on it' with owns {button:true, up:false}, up at left 328 right 352 top 4.5; chrome 3.12 4/4 and 3.14 3/4. Passed on #608's own CI. Introduced by #608 review-A A4 (mb-igva).
