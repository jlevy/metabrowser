---
type: is
id: is-01m2nz79vrjb2vpp5ydxra84e5
title: Correct repository-source and shared provider-mirror architecture
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - design
dependencies:
  - type: blocks
    target: is-01m2nz8q666pwqcbxbn7d5jr6x
  - type: blocks
    target: is-01m2nz8zzgxsw9yzsgekxy82sr
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:41:07.187Z
updated_at: 2026-09-16T20:42:02.606Z
started_at: 2026-09-16T20:41:25.748Z
---
Replace the unreleased pinned-checkout, detached-worktree, and entry-owned provider-cache design with three independent layers: session repository subjects, one shared worktree-free Git object store, and one stable-repository/auth-scoped provider mirror. Update the long-lived architecture, both active plans, the route/source boundaries, phase sequencing, acceptance tests, and all affected implementation beads. Publish the result as one formally stacked GitHub PR above Phase 0C.2, run independent review and make verify, record the exact stack/PR evidence, and do not merge.
