---
type: is
id: is-01m7kgg2g37gev8jgq5rsf7kk2
title: "PR #490 B1: A1's call site in fetchRootSummary has no browserless guard"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T01:03:46.178Z
updated_at: 2026-11-17T01:04:00.337Z
started_at: 2026-11-17T01:04:00.335Z
---
Low, PR #490 review B (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5930582691). root-summary-refresh-session.js answered every request with no tally status, so replacing fetchRootSummary's status argument with a settled one passed every browserless session.
