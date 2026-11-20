---
type: is
id: is-01m7wy6mgsaf00wb9khzknj5ym
title: "PR #656 A3: unminted cursor/key/limit raises instead of bad_query"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wy6kbgkfyg4kf94bk8z11e
hold: null
hold_until: null
created_at: 2026-11-20T16:56:26.905Z
updated_at: 2026-11-20T18:12:02.657Z
started_at: 2026-11-20T17:22:57.394Z
closed_at: 2026-11-20T18:12:02.657Z
close_reason: fixed in 7868d4844; CI green at ee5f72c6b; dispositions https://github.com/jlevy/metabrowser/pull/656#issuecomment-7047094985
resolution: null
duplicate_of: null
---
Severity Medium. PR #656 review A (https://github.com/jlevy/metabrowser/pull/656#pullrequestreview-5996326781). source.py _cursor_point/_start; table_source.py parse_position_key/parse_positional_cursor/limit.
