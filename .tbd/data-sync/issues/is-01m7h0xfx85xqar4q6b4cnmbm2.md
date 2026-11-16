---
type: is
id: is-01m7h0xfx85xqar4q6b4cnmbm2
title: "PR #455 B5: startup_style_server_ms_max now reads a larger quantity for a stamped /static stylesheet"
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
created_at: 2026-11-16T01:52:59.815Z
updated_at: 2026-11-16T02:11:21.077Z
started_at: 2026-11-16T01:53:16.333Z
closed_at: 2026-11-16T02:11:21.076Z
close_reason: "B5 fixed in bea3f5c25 and d5356550a: note beside startup_style_server_ms_max in both budget files; protocol compares by end of body."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B5. References: explorations/performance-loop/probe.js:139-144, :657-660; performance-budgets.toml:255-258; encoded_assets.py:162-182.
