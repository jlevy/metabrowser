---
type: is
id: is-01m7h0xmpvz2vetsc00jdm3gv5
title: "PR #455 C3: run.py's read-back accepts a truncated body"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:53:04.730Z
updated_at: 2026-11-16T02:11:24.140Z
started_at: 2026-11-16T01:53:20.176Z
closed_at: 2026-11-16T02:11:24.138Z
close_reason: "C3 fixed in bea3f5c25: _served_body refuses a body shorter than its Content-Length; test fails before and passes after."
resolution: null
duplicate_of: null
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review C (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914139612), finding C3. References: explorations/performance-loop/run.py:820-838.
