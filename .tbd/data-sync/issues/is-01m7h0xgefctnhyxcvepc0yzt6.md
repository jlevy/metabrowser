---
type: is
id: is-01m7h0xgefctnhyxcvepc0yzt6
title: "PR #455 B6: the measurement beside MAX_ENCODED_ASSET_BYTES describes the files, not what the store can hold"
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
created_at: 2026-11-16T01:53:00.366Z
updated_at: 2026-11-16T02:11:21.456Z
started_at: 2026-11-16T01:53:16.724Z
closed_at: 2026-11-16T02:11:21.455Z
close_reason: "B6 fixed in 5ba8a1846: per-path maxima, one-landing figures and held_bytes beside MAX_ENCODED_ASSET_BYTES."
resolution: null
duplicate_of: null
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B6. References: src/metabrowser/encoded_assets.py:46-56.
