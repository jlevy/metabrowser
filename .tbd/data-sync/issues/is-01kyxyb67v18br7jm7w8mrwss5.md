---
type: is
id: is-01kyxyb67v18br7jm7w8mrwss5
title: "P1: add client-side fuzzy quick file finder"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxybpctnfvcbj8eh629hab0
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
created_at: 2026-08-01T05:56:54.138Z
updated_at: 2026-08-01T05:57:10.681Z
---
Implement the DOM-independent search controller, known-file catalog, deterministic fuzzy scorer, local provider, and slash-key accessible palette. Search every file path observed through initial and lazy tree responses, Recent, scoped events, and successful navigation. Report incomplete local coverage, reuse navigateToPath, handle stale candidates, keep all search work client-side, and verify responsiveness and keyboard behavior.
