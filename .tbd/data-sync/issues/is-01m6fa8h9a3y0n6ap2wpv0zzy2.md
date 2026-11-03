---
type: is
id: is-01m6fa8h9a3y0n6ap2wpv0zzy2
title: "PR #279 B4: PullList.fetched_at is pattern-checked, not parsed, and _state parses it"
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
created_at: 2026-11-02T23:42:08.169Z
updated_at: 2026-11-03T00:12:59.912Z
started_at: 2026-11-02T23:50:21.795Z
closed_at: 2026-11-03T00:12:59.911Z
close_reason: "fixed in 24f9b01d: fetched_at is parsed by a validator. Disposition: https://github.com/jlevy/metabrowser/pull/279#issuecomment-6591830966"
resolution: null
duplicate_of: null
---
pull_list.py:188; pull_list_route.py:283. Suggestion, Low. Review B: https://github.com/jlevy/metabrowser/pull/279#pullrequestreview-5744768671
