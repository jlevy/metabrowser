---
type: is
id: is-01m7hh0n8q04fm9w8ryw8vwqnv
title: "PR #466 A3: grouped-load lifecycle is a browser state machine only Chrome exercises"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:20.822Z
updated_at: 2026-11-16T06:34:33.212Z
started_at: 2026-11-16T06:34:33.211Z
---
Medium. app.js:1280-1365, :1526-1539, :9210. Review A https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915498910. Fix: createGroupedLoads in tree-filter-model.js with four browserless session cases in the golden.
