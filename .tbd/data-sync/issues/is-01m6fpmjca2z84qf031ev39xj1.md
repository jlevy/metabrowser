---
type: is
id: is-01m6fpmjca2z84qf031ev39xj1
title: "PR #283 D6: the Python pull-page session test reads only the first part of the session"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T03:18:25.417Z
updated_at: 2026-11-03T03:28:54.588Z
started_at: 2026-11-03T03:18:38.120Z
closed_at: 2026-11-03T03:28:54.587Z
close_reason: "fixed in 0098e113 on PR #283: D6 session test runs --part all and asserts the second part"
resolution: null
duplicate_of: null
---
Low (suggestion). Review D, PR #283, https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5746541377. tests/test_github_pull_page_session.py:391 runs run_session('github-pull-page-session.js') with no --part, which prints the first part only, so the second part's keys are under no Python assertion.
