---
type: is
id: is-01m6f2kwkpby7yjqrvp5t3zbjk
title: "PR #274 A6: script-spawn guard matches git as a substring"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kt0jwn6mx6es1wg9w3b8
hold: null
hold_until: null
created_at: 2026-11-02T21:28:31.604Z
updated_at: 2026-11-02T21:50:26.489Z
started_at: 2026-11-02T21:28:35.705Z
closed_at: 2026-11-02T21:50:26.488Z
close_reason: "fixed in 11056d3; confirmed by test_the_script_check_reads_git_as_a_word. Reply: https://github.com/jlevy/metabrowser/pull/274#issuecomment-6589345714"
resolution: null
duplicate_of: null
---
Suggestion. tests/test_git_hook_environment.py test_no_script_a_golden_can_run_starts_git. Review A: https://github.com/jlevy/metabrowser/pull/274#pullrequestreview-5743230239
