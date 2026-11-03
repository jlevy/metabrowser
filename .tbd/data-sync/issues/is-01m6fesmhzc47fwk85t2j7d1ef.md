---
type: is
id: is-01m6fesmhzc47fwk85t2j7d1ef
title: "PR #283 C3: an unreadable lender has every ref swept"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
created_at: 2026-11-03T01:01:22.878Z
updated_at: 2026-11-03T01:01:22.878Z
---
Medium. Review C. lender.py:614-654, 674-689. Sweep only when the lender was readable in this pass.
