---
type: is
id: is-01kzz4dt2aa6059jzk41yszq49
title: "Route C: Integrate browser history and remove hash file routing"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dtbr1k1339614faee95w
parent_id: is-01kzz03fmd769zawq6gf5d1hd7
created_at: 2026-08-14T03:18:07.689Z
updated_at: 2026-08-14T03:18:07.992Z
---
Compose the canonical route module with app.js and selectFile. Initialize from pathname, push normal file and folder navigation, replace only startup or folder-slash canonicalization, restore with popstate, and avoid refetching same-file fragment changes. Delete parseHashRoute, splitHashRoute, hash file heuristics, hashchange file navigation, legacy migration, and their tests. Add focused DOM tests for direct load, back/forward, reload-equivalent state, folders, and fragments.
