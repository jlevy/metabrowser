---
type: is
id: is-01m6fa8hnmcbdrdtrjyskqp9xj
title: "PR #279 C1: a stored page mark's etag is not held to the grammar gh_api enforces"
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
created_at: 2026-11-02T23:42:08.563Z
updated_at: 2026-11-03T00:13:00.234Z
started_at: 2026-11-02T23:50:21.466Z
closed_at: 2026-11-03T00:13:00.233Z
close_reason: "fixed in 24f9b01d: ListPageMark.etag has gh_api's grammar. Disposition: https://github.com/jlevy/metabrowser/pull/279#issuecomment-6591831335"
resolution: null
duplicate_of: null
---
pull_list.py:171; gh.py:384-385. Severity Low. Review C: https://github.com/jlevy/metabrowser/pull/279#pullrequestreview-5744962193
