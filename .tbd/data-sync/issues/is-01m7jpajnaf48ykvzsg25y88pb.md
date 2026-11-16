---
type: is
id: is-01m7jpajnaf48ykvzsg25y88pb
title: "PR #477 A3: the heading's same-name guard never matches a name with a quote"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7jjcfgz5r5ykt72449xb6as
hold: null
hold_until: null
created_at: 2026-11-16T17:26:23.143Z
updated_at: 2026-11-16T17:28:20.876Z
started_at: 2026-11-16T17:28:20.875Z
---
Low. app.js:262-265 compares innerHTML with esc'd markup; source pin tests/test_browser_client_filestore.py:926-929. Review A (round 1), PR #477: https://github.com/jlevy/metabrowser/pull/477#pullrequestreview-5923748713
