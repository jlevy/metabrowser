---
type: is
id: is-01m7hh0tcx8k99jk34ctm5hw51
title: "PR #466 B2: grouped route builds every tree and the JSON in one event-loop turn"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:26.076Z
updated_at: 2026-11-16T06:34:37.176Z
started_at: 2026-11-16T06:34:37.175Z
---
Low. server.py:2478-2511. Review B https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915875839. Fix: yield between groups and measure.
