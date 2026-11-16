---
type: is
id: is-01m7h0xhbkrtvt5hrq2h0ahvbe
title: "PR #455 B8: a cold stamped /static file over 64 KB is no longer streamed"
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
created_at: 2026-11-16T01:53:01.298Z
updated_at: 2026-11-16T02:11:21.848Z
started_at: 2026-11-16T01:53:17.473Z
closed_at: 2026-11-16T02:11:21.847Z
close_reason: B8 fixed in 5ba8a1846 (module docstring) and d5356550a (80 ms-link arm in the protocol).
resolution: null
duplicate_of: null
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B8. References: src/metabrowser/encoded_assets.py:174-182.
