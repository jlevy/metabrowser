---
type: is
id: is-01kxj6mrvpkqnkn274rhy3mg2j
title: "Spec: Archive contents and browsing archives as folders"
kind: epic
status: in_progress
priority: 2
version: 17
spec_path: docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md
delegate: claude-code@spud10.local
labels:
  - linear
  - Feature
dependencies: []
parent_id: null
child_order_hints:
  - is-01m0dkj0xzgg9b6kc7ge0fm2ne
  - is-01m885867jg0s1fy2w9f8dwzrd
  - is-01m885941n5xs6ap60sm1avesc
  - is-01m885969bezeyfe7tcepdtszx
  - is-01m8859a9ayeznqbj36nj10470
  - is-01m8859dc4ryxnv13b7br1vvk0
  - is-01m8859hheaevf06jatbqce8ja
  - is-01m8859m23q37fyv4kk33pp5qq
hold: null
hold_until: null
created_at: 2026-07-15T06:15:21.716Z
updated_at: 2026-11-25T01:32:03.522Z
started_at: 2026-11-25T01:30:45.263Z
extensions:
  linear:
    id: 7fe6f65e-3f29-477c-9c54-3bcd91ae211a
    linked_at: 2026-11-25T01:31:41.259Z
---
Effort epic for archive support (ZIP and every ZIP-based format by its bytes; tar, and tar compressed with gzip, bzip2, or xz), planned in docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md.

Phase 1: an archive kind whose Contents view lists the members as a tree on the archive's own file page, with a summary and problem counts.
Phase 2: archives expand in the navigation tree like folders, and members open with their own kinds' views, through two new generic plugin surfaces (member sources, and folder-like container children).

Safety requirements carried from TODO.md: safe member paths, symlink and traversal rejection, duplicate-name behavior, nesting limits, and aggregate decompression limits, all before members are readable.
