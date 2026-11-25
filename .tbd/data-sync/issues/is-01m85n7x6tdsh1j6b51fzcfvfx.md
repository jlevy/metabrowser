---
type: is
id: is-01m85n7x6tdsh1j6b51fzcfvfx
title: "Rendered diff: read KPress's meta[\"kpress_classes\"] so an added task list or a newly boxed item is not source_only"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-11-24T02:13:01.272Z
updated_at: 2026-11-25T02:35:16.691Z
---
KPress 0.3.10 (jlevy/kpress#82, pinned by commit on #771) lists the classes it appends to a task item and list in meta["kpress_classes"] on list_item_open and bullet_list_open. markdown_projection drops item and list classes in its allowlist because it could not tell KPress's from attribute syntax, so a task list a change adds, or an item that gains its box, is source_only (arch-diff-pipeline.md, Task lists). Use kpress_classes to separate KPress's classes from the author's, so those changes render in Rendered.
