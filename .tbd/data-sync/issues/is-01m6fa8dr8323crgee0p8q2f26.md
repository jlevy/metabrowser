---
type: is
id: is-01m6fa8dr8323crgee0p8q2f26
title: "PR #279 A1: a more that joins a running refresh is silently dropped (also Qodo r4448629460)"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fa7swqbvb8yz7s1jdykmj8
hold: null
hold_until: null
created_at: 2026-11-02T23:42:04.550Z
updated_at: 2026-11-03T00:12:57.002Z
started_at: 2026-11-02T23:44:24.645Z
closed_at: 2026-11-03T00:12:57.000Z
close_reason: "fixed in 2e61ef2b: a more that joins a job is kept and read after its refresh, in the same job. Disposition: https://github.com/jlevy/metabrowser/pull/279#issuecomment-6591830620"
resolution: null
duplicate_of: null
---
pull_list_route.py:410-415 start_refresh answers joined before reading ask.more. Severity Medium. Review A: https://github.com/jlevy/metabrowser/pull/279#pullrequestreview-5744581294 Qodo: https://github.com/jlevy/metabrowser/pull/279#discussion_r4448629460
