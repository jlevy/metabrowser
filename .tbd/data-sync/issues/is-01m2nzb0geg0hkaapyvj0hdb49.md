---
type: is
id: is-01m2nzb0geg0hkaapyvj0hdb49
title: "Repository source foundation review: publish immutable Git-tree PR"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - stack:publication
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:43:08.685Z
updated_at: 2026-09-16T21:12:28.728Z
started_at: 2026-09-16T21:12:28.728Z
---
Independently review RepositorySubject, ContentSource, GitCommandTarget, the shared worktree-free store, and full-OID tree/blob serving. Resolve findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green acquisition head. Prove concurrent subjects, batch-reader lifecycle, no checkout/index/worktree creation, CLI parity, and architecture-map coverage. Record PR URL, base/head branches and OIDs, formal stack view, review evidence, and final green CI. Do not merge.
