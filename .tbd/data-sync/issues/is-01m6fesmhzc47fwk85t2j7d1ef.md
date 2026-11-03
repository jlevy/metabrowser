---
type: is
id: is-01m6fesmhzc47fwk85t2j7d1ef
title: "PR #283 C3: an unreadable lender has every ref swept"
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
created_at: 2026-11-03T01:01:22.878Z
updated_at: 2026-11-03T01:54:03.997Z
started_at: 2026-11-03T01:33:06.887Z
closed_at: 2026-11-03T01:54:03.996Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: C3 unreadable lender refused before the sweep; refs stay"
resolution: null
duplicate_of: null
---
Medium. Review C. lender.py:614-654, 674-689. Sweep only when the lender was readable in this pass.
