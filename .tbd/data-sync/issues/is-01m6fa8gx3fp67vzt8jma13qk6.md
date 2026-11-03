---
type: is
id: is-01m6fa8gx3fp67vzt8jma13qk6
title: "PR #279 B3: a crash between the list write and the stamp write labels a fresh list stale"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fa7swqbvb8yz7s1jdykmj8
hold: null
hold_until: null
created_at: 2026-11-02T23:42:07.778Z
updated_at: 2026-11-03T00:12:59.592Z
started_at: 2026-11-02T23:48:38.868Z
closed_at: 2026-11-03T00:12:59.591Z
close_reason: "fixed in 7882a295: a stamp older than the list says nothing of it. Disposition: https://github.com/jlevy/metabrowser/pull/279#issuecomment-6591830966"
resolution: null
duplicate_of: null
---
pull_list_refresh.py:279,305,310; pull_list_route.py:285. Severity Low. Review B: https://github.com/jlevy/metabrowser/pull/279#pullrequestreview-5744768671
