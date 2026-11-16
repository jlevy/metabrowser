---
type: is
id: is-01m7jpajnaf48ykvzsg25y88pb
title: "PR #477 A3: the heading's same-name guard never matches a name with a quote"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7jjcfgz5r5ykt72449xb6as
hold: null
hold_until: null
created_at: 2026-11-16T17:26:23.143Z
updated_at: 2026-11-16T17:46:12.258Z
started_at: 2026-11-16T17:28:20.875Z
closed_at: 2026-11-16T17:46:12.248Z
close_reason: "Fixed in c1b48908d (PR #477 review A): guard compares pathEl.textContent with pathBaseName(root); source-kind-session asserts no rewrite for a quoted name (fails on the old guard); source pin updated. Disposition reply: https://github.com/jlevy/metabrowser/pull/477#issuecomment-6924312625"
resolution: null
duplicate_of: null
---
Low. app.js:262-265 compares innerHTML with esc'd markup; source pin tests/test_browser_client_filestore.py:926-929. Review A (round 1), PR #477: https://github.com/jlevy/metabrowser/pull/477#pullrequestreview-5923748713
