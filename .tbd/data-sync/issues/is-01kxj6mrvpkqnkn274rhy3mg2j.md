---
type: is
id: is-01kxj6mrvpkqnkn274rhy3mg2j
title: "Spec: Archive contents and browsing archives as folders"
kind: epic
status: in_progress
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md
delegate: claude-code@spud10.local
labels:
  - linear
  - Feature
dependencies: []
parent_id: null
child_order_hints:
  - is-01m0dkj0xzgg9b6kc7ge0fm2ne
hold: null
hold_until: null
created_at: 2026-07-15T06:15:21.716Z
updated_at: 2026-11-25T01:31:29.801Z
started_at: 2026-11-25T01:30:45.263Z
extensions:
  linear:
    id: 7fe6f65e-3f29-477c-9c54-3bcd91ae211a
    linked_at: 2026-11-25T01:31:29.801Z
---
Effort epic for archive support (ZIP and every ZIP-based format by its bytes; tar, and tar compressed with gzip, bzip2, or xz), planned in docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md.

Phase 1: an archive kind whose Contents view lists the members as a tree on the archive's own file page, with a summary and problem counts.
Phase 2: archives expand in the navigation tree like folders, and members open with their own kinds' views, through two new generic plugin surfaces (member sources, and folder-like container children).

Safety requirements carried from TODO.md: safe member paths, symlink and traversal rejection, duplicate-name behavior, nesting limits, and aggregate decompression limits, all before members are readable.
