---
type: is
id: is-01m7wztr8mpkr8braes7adb6js
title: test_golden_pin_age_groups puts every file in Older though the clock is pinned 3 h after the tip (cause under investigation)
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T17:24:54.674Z
updated_at: 2026-11-20T17:24:54.674Z
---
Failed on main run 44779757308 (unit 3.12 1/2, unit 3.14t 1/2, at 1e137be1a) and PR 662 run 44781044946 (unit 3.12 1/2, unit 3.14 1/2): tests/test_cli_git_pin_golden.py:716 groups == [('older', 7)], expected [('24h', 1), ('older', 6)]; ages state ready, 7 files, 7 dated. The test monkeypatches content_routes._request_instant to AGES_TIP + 3h. Passed on other runs of the same commits.
