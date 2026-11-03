---
type: is
id: is-01m6fesfkd5aspqj488a0z8sav
title: "PR #283 A5: overlay fetch preparation seam written twice with different failure policy"
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
created_at: 2026-11-03T01:01:17.804Z
updated_at: 2026-11-03T01:53:59.860Z
started_at: 2026-11-03T01:33:02.666Z
closed_at: 2026-11-03T01:53:59.859Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: A5 one seam overlay_fetch_arguments with one failure policy"
resolution: null
duplicate_of: null
---
Medium. Review A. pull_refs.py:282-297 and update.py:618-641. One helper in lender.py with one policy for an unreadable record.
