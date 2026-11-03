---
type: is
id: is-01m6fesgqaqmpv4cjsekhhvq5a
title: "PR #283 A8: PR body claims a guarded test that folders do not import the lender"
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
created_at: 2026-11-03T01:01:18.953Z
updated_at: 2026-11-03T01:54:00.870Z
started_at: 2026-11-03T01:33:03.651Z
closed_at: 2026-11-03T01:54:00.869Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: A8 folder import guard names the lender; proved failing when the server imports it"
resolution: null
duplicate_of: null
---
Low. Review A. Check tests/test_cache_layout.py first; add a real guard or drop the claim.
