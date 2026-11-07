---
type: is
id: is-01m6sq0zex3pr3hngsdmwfayy6
title: "Autocomplete pull requests with a Quick Search # prefix"
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T00:37:36.346Z
updated_at: 2026-11-07T00:39:19.741Z
started_at: 2026-11-07T00:39:19.398Z
---
In GitHub Quick Search, # suggests recent PRs across all states, #words matches titles, and #digits matches number prefixes with the exact number first. Preserve bare number and ordinary file search. Keep the catalog incremental and result windows bounded, and verify actual keyboard navigation in both source modes.

## Notes

Backend and palette are in parallel implementation. The design and browser playbook specify recent all-state matches, case-insensitive titles, indexed number prefixes and exact-first ordering.
