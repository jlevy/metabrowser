---
type: is
id: is-01m6fpmh5pj6dfepd20jx8726s
title: "PR #283 D3: a permission error during a --checkout repair prints a traceback"
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
created_at: 2026-11-03T03:18:24.181Z
updated_at: 2026-11-03T03:28:53.413Z
started_at: 2026-11-03T03:18:37.088Z
closed_at: 2026-11-03T03:28:53.412Z
close_reason: "fixed in f39f91e0 on PR #283: D3 _rebind maps OSError to AcquisitionError, an Error: line; same command repairs"
resolution: null
duplicate_of: null
---
Medium. Review D, PR #283, https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5746541377. src/metabrowser/cache/acquire.py:1139-1162 (_rebind) calls rebind_lender and write_record_atomic with no OSError handling; cli/git_pin_cli.py:87 and cli/acquire_cli.py:49-57 carry neither OSError nor PermissionError. objects/info read-only gave a PermissionError traceback.
