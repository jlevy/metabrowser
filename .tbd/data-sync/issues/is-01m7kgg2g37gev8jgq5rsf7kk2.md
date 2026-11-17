---
type: is
id: is-01m7kgg2g37gev8jgq5rsf7kk2
title: "PR #490 B1: A1's call site in fetchRootSummary has no browserless guard"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T01:03:46.178Z
updated_at: 2026-11-17T02:33:15.739Z
started_at: 2026-11-17T01:04:00.335Z
closed_at: 2026-11-17T02:33:15.738Z
close_reason: "fixed in 0855877 on PR #490 (CI run 43992596826 green); disposition: https://github.com/jlevy/metabrowser/pull/490#issuecomment-6936212343"
resolution: null
duplicate_of: null
---
Low, PR #490 review B (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5930582691). root-summary-refresh-session.js answered every request with no tally status, so replacing fetchRootSummary's status argument with a settled one passed every browserless session.
