---
type: is
id: is-01m6sq0zex3pr3hngsdmwfayy6
title: "Autocomplete pull requests with a Quick Search # prefix"
kind: feature
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6sqgkmrvgmdx0htfvr7xnv3
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T00:37:36.346Z
updated_at: 2026-11-07T04:18:59.578Z
started_at: 2026-11-07T00:39:19.398Z
closed_at: 2026-11-07T04:18:59.577Z
close_reason: "PR #314 at 5c1fdb0f is mergeable with green exact-head CI and zero unresolved threads. Prefix/title/exact-number ordering and both repository modes passed browser and automated sessions. Ready for owner merge in stack #302."
resolution: null
duplicate_of: null
---
In GitHub Quick Search, # suggests recent PRs across all states, #words matches titles, and #digits matches number prefixes with the exact number first. Preserve bare number and ordinary file search. Keep the catalog incremental and result windows bounded, and verify actual keyboard navigation in both source modes.

## Notes

Implemented and verified both modes with real catalog data. In the managed browser #checks showed open and merged title matches and #30 ranked the exact PR before #309 and other prefixes. Enter opened Conversation and Back restored Files. The existing checkout accepted #29 and keyboard-selected #299. A plain folder still completed #report.md. Focused backend, frontend, and golden checks passed.
