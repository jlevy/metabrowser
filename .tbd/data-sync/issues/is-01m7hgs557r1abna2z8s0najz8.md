---
type: is
id: is-01m7hgs557r1abna2z8s0najz8
title: "PR #471 A6: the label routes cannot see a read running inside the catalog job"
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
created_at: 2026-11-16T06:30:14.950Z
updated_at: 2026-11-16T07:22:39.340Z
started_at: 2026-11-16T06:30:40.984Z
closed_at: 2026-11-16T07:22:39.339Z
close_reason: "fixed in 0ef7899 by the move: the only read is the job under labels_job_key; https://github.com/jlevy/metabrowser/pull/471#issuecomment-6910120170"
resolution: null
duplicate_of: null
---
Low. pull_labels_route.py:55-65, :128-137; pull_labels.py:253-256, :476-481. PR #471 Review A: https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915672676
