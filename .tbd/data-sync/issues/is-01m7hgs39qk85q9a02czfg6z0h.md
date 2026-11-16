---
type: is
id: is-01m7hgs39qk85q9a02czfg6z0h
title: "PR #471 A2: the label set is read by age inside the catalog job's critical path"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjw3fwhayb3tmmt9prx9m
hold: null
hold_until: null
created_at: 2026-11-16T06:30:13.046Z
updated_at: 2026-11-16T06:30:39.489Z
started_at: 2026-11-16T06:30:39.489Z
---
Medium. pull_list_refresh.py:569-576; pull_labels.py:374-380, :505-522. Coordinator chose option (a): an on-demand read in its own job under labels_job_key. PR #471 Review A: https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915672676
