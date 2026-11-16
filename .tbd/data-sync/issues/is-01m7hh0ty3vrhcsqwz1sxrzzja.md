---
type: is
id: is-01m7hh0ty3vrhcsqwz1sxrzzja
title: "PR #466 B3: MAX_TREE_GROUPS admits reads that take 8 s and 667 MB"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:26.626Z
updated_at: 2026-11-16T07:26:36.829Z
started_at: 2026-11-16T06:34:37.548Z
closed_at: 2026-11-16T07:26:36.828Z
close_reason: "fixed in 6ac888a and 364c078 (MAX_TREE_GROUPS = 8 with the measurement); PR #466 review B"
resolution: null
duplicate_of: null
---
Low. contract.py:100-102, :1079-1080. Review B https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915875839. Coordinator: set to 8 with the measurement.
