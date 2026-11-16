---
type: is
id: is-01m7hgs7gan2ztr4c2k8cqsm1p
title: "PR #471 A11: a 304 keeps a page's old continuation, so a full last page never reads a new page"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjw3fwhayb3tmmt9prx9m
hold: null
hold_until: null
created_at: 2026-11-16T06:30:17.353Z
updated_at: 2026-11-16T07:22:41.020Z
started_at: 2026-11-16T06:30:42.931Z
closed_at: 2026-11-16T07:22:41.019Z
close_reason: "fixed in c516310: a 304's has_next from its Link; StackPage deferred as mb-1648; https://github.com/jlevy/metabrowser/pull/471#issuecomment-6910120170"
resolution: null
duplicate_of: null
---
Low. pull_labels.py:434-438, :519-521. Refined by Review B. PR #471 Review A: https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915672676
