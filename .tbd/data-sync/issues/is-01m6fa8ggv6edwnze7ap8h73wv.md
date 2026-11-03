---
type: is
id: is-01m6fa8ggv6edwnze7ap8h73wv
title: "PR #279 B2: a successful more restarts the window the automatic refresh waits for, while the list reads stale"
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
created_at: 2026-11-02T23:42:07.387Z
updated_at: 2026-11-03T00:12:59.257Z
started_at: 2026-11-02T23:48:38.534Z
closed_at: 2026-11-03T00:12:59.256Z
close_reason: "fixed in 7882a295: a success is stamped as of the list's fetched_at. Disposition: https://github.com/jlevy/metabrowser/pull/279#issuecomment-6591830966"
resolution: null
duplicate_of: null
---
pull_list_refresh.py:249,307-310; pull_list.py:315; pull_list_route.py:283-284. Severity Low. Review B: https://github.com/jlevy/metabrowser/pull/279#pullrequestreview-5744768671
