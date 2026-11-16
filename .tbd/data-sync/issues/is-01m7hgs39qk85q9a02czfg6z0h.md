---
type: is
id: is-01m7hgs39qk85q9a02czfg6z0h
title: "PR #471 A2: the label set is read by age inside the catalog job's critical path"
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
created_at: 2026-11-16T06:30:13.046Z
updated_at: 2026-11-16T07:22:37.968Z
started_at: 2026-11-16T06:30:39.489Z
closed_at: 2026-11-16T07:22:37.967Z
close_reason: "fixed in 0ef7899: option (a), on-demand job under labels_job_key, started only by labels-refresh; real-gh re-read measured; https://github.com/jlevy/metabrowser/pull/471#issuecomment-6910120170"
resolution: null
duplicate_of: null
---
Medium. pull_list_refresh.py:569-576; pull_labels.py:374-380, :505-522. Coordinator chose option (a): an on-demand read in its own job under labels_job_key. PR #471 Review A: https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915672676
