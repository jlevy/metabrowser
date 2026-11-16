---
type: is
id: is-01m7h0xfe7t50nkvv4c5ga0hgb
title: "PR #455 B4: U2 busy and phase totals are wall-clock time, which (a)'s move of work between contexts cannot be compared in"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:52:59.334Z
updated_at: 2026-11-16T01:53:15.939Z
started_at: 2026-11-16T01:53:15.938Z
---
Severity: Medium. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B4. References: explorations/performance-loop/README.md:1578-1582; server-time-sums.mjs:135-153; server_timing.py:126-140; server.py:3894-3895; plugin_loader/static_assets.py:138-139; encoded_assets.py:94-96.
