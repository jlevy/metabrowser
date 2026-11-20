---
type: is
id: is-01m7wztr8mpkr8braes7adb6js
title: test_serve_pin forgot content_routes from sys.modules and left the package attribute on the re-import, so a later clock patch missed the server's module
kind: bug
status: closed
priority: 2
version: 7
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T17:24:54.674Z
updated_at: 2026-11-20T18:02:22.691Z
closed_at: 2026-11-20T18:02:22.689Z
close_reason: "Mechanism (a forgotten module's re-import left the package attribute on the copy) fixed on main by #664 (947f314f3, forget_module, mb-6byq); duplicate #665 closed."
resolution: null
duplicate_of: null
---
Failed on main run 44779757308 (unit 3.12 1/2, unit 3.14t 1/2, at 1e137be1a) and PR 662 run 44781044946 (unit 3.12 1/2, unit 3.14 1/2): tests/test_cli_git_pin_golden.py:716 groups == [('older', 7)], expected [('24h', 1), ('older', 6)]; ages state ready, 7 files, 7 dated. The test monkeypatches content_routes._request_instant to AGES_TIP + 3h. Passed on other runs of the same commits.

## Notes

2026-11-20 audit: same failure as mb-6byq (test_golden_pin_age_groups, groups [('older', 7)] with the patched clock apparently not in effect), which has three CI sightings on Python 3.12, 3.13 and 3.14t. Left open because this bead was filed minutes before the audit and may be under investigation; close whichever is not kept.
