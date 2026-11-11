---
type: is
id: is-01m7594w0k9pn05dh0kjp69jrh
title: "PR #348 E8: an automatic refresh of the same PR joins idle work and reads nothing"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7594pkfe0xdkwhjqrwwpxz2
hold: null
hold_until: null
created_at: 2026-11-11T12:25:57.010Z
updated_at: 2026-11-11T14:23:39.142Z
started_at: 2026-11-11T12:25:57.614Z
closed_at: 2026-11-11T14:23:39.141Z
close_reason: "Fixed: f9f7b9c3. An automatic request finding only idle work goes through the staleness check and, when due, promotes the job (host.start). Test: test_a_due_automatic_refresh_promotes_idle_work_to_a_metadata_read (fails without the change)."
resolution: null
duplicate_of: null
---
Low. pull_route.py:690-693; served_pull.py:270-306. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040
