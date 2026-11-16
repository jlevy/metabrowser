---
type: is
id: is-01m7hgs4pf94n2hnnyfnfm5pp1
title: "PR #471 A5: the label set copies the native stack snapshot, and the copies drift"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjw3fwhayb3tmmt9prx9m
hold: null
hold_until: null
created_at: 2026-11-16T06:30:14.477Z
updated_at: 2026-11-16T07:22:39.003Z
started_at: 2026-11-16T06:30:40.613Z
closed_at: 2026-11-16T07:22:39.002Z
close_reason: "fixed in 33f05d1 and 0ef7899: repository_snapshot.py shared by pull_stacks and pull_labels; source check in publish_labels; https://github.com/jlevy/metabrowser/pull/471#issuecomment-6910120170"
resolution: null
duplicate_of: null
---
Medium. pull_labels.py:105-587 vs pull_stacks.py:68-399; pull_labels_route.py vs pull_stacks_route.py. PR #471 Review A: https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915672676
