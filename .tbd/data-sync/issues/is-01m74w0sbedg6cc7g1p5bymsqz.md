---
type: is
id: is-01m74w0sbedg6cc7g1p5bymsqz
title: "PR #348 A13: production signatures shaped around test doubles"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:31.725Z
updated_at: 2026-11-11T10:57:53.811Z
started_at: 2026-11-11T09:24:55.937Z
closed_at: 2026-11-11T10:57:53.810Z
close_reason: "Fixed: c1720244 (_fetch passes exact unconditionally; fetch_commit always rechecks), bd79d8d0 + cff5c204 (write_pull_refresh requires the observation; only a record or not_cached observes the disk)."
resolution: null
duplicate_of: null
---
Low. pull_refs.py:357-362; fetch_commit(if_missing=False); write_pull_refresh(expected=None). Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
