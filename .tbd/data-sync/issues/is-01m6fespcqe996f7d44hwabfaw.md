---
type: is
id: is-01m6fespcqe996f7d44hwabfaw
title: "PR #283 C8: --api /api/cache/... ignores --checkout on a hit and says nothing"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T01:01:24.758Z
updated_at: 2026-11-03T01:54:05.599Z
started_at: 2026-11-03T01:33:08.444Z
closed_at: 2026-11-03T01:54:05.598Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: C8 cache route says --checkout is not applied"
resolution: null
duplicate_of: null
---
Low. Review C. acquire.py:1047; acquire_cli.py run_api_after_acquire.
