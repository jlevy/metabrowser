---
type: is
id: is-01m7kdd7txfkyanyw0rnwjv6pw
title: "PR #490 A1: a provisional tally decides whether the held ignored line stays"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T00:09:47.613Z
updated_at: 2026-11-17T00:09:56.403Z
started_at: 2026-11-17T00:09:56.402Z
---
Medium, PR #490 review A (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5929928725). app.js fetchRootSummary adopted every depth=0 summary, including tally_cache_status scanning, so a mid-walk 'nothing ignored yet' released the held line and the tree rose then dropped.
