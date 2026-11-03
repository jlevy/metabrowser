---
type: is
id: is-01m6fa8fr2e04w5bd0fz2v8h43
title: "PR #279 A6: an unexpected exception in the job leaves no stamp, so it is retried on every poll"
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
created_at: 2026-11-02T23:42:06.593Z
updated_at: 2026-11-03T00:12:58.622Z
started_at: 2026-11-02T23:50:21.129Z
closed_at: 2026-11-03T00:12:58.621Z
close_reason: "fixed in 24f9b01d: a gh_failed stamp with a fixed message, then re-raised. Disposition: https://github.com/jlevy/metabrowser/pull/279#issuecomment-6591830620"
resolution: null
duplicate_of: null
---
pull_list_route.py:378-386 _run_refresh. Suggestion, Low. Review A: https://github.com/jlevy/metabrowser/pull/279#pullrequestreview-5744581294
