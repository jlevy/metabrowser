---
type: is
id: is-01kzz47famwdxwjh0yphhxj049
title: "PR #35 review R3: nav-shortcut-hints names a role-less div"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:40.083Z
updated_at: 2026-08-14T03:32:02.428Z
closed_at: 2026-08-14T03:32:02.428Z
close_reason: "Fixed in 78ee53e: nav-shortcut-hints now carries role=group, asserted in test_browser_recent_ui.py."
---
src/metabrowser/server.py:983-984 puts aria-label on a plain div (role=generic), which ARIA forbids naming, so assistive tech drops the label. Add role=group and assert it in tests/test_browser_recent_ui.py.
