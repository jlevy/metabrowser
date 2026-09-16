---
type: is
id: is-01m2nz8q666pwqcbxbn7d5jr6x
title: Repository content-source contract for filesystem and immutable Git revisions
kind: feature
status: in_progress
priority: 1
version: 4
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
  - type: blocks
    target: is-01m0dkj0gqvpzpxm7t1tpshf30
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:41:53.605Z
updated_at: 2026-09-16T21:24:53.260Z
started_at: 2026-09-16T21:24:53.260Z
---
Introduce the application-level RepositorySubject and ContentSource boundary before Git revision serving. Add AttachedFilesystemSubject and GitRevisionSubject; a trusted GitCommandTarget accepted by run_git/spawn_git_process; immutable Git tree enumeration and bounded blob reads without fake mtimes, watchers, ignore state, or writable paths; and route/inventory lifecycle integration that does not require every root to be a Path. Preserve the exact-root containment gate for attached filesystems. Add CLI parity and goldens, two-subject concurrency tests, batch-reader lifecycle/cancellation, and architecture-map updates. This bead blocks mb-z335; no checkout, index, branch switch, or worktree creation is allowed.
