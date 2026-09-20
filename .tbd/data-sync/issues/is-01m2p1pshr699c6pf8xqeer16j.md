---
type: is
id: is-01m2p1pshr699c6pf8xqeer16j
title: "Repository library Phase 1B-a review: publish worktree-free acquisition PR"
kind: task
status: in_progress
priority: 1
version: 16
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m2nz8q666pwqcbxbn7d5jr6x
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.927Z
updated_at: 2026-09-20T05:50:02.876Z
started_at: 2026-09-16T21:24:54.760Z
---
Independently review GitCommandTarget, file:// local-origin sources under the untrusted profile (mb-dxmb), worktree-free acquisition, source/store alias publication, ref/object validation, crash recovery, cross-process CAS behavior, CLI parity, and acquisition goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 1A head. Record exact stack evidence and final green CI. Do not merge.

## Notes

Survivor PR is draft #217 https://github.com/jlevy/metabrowser/pull/217
Parent: #140 claude/v011-cache-format-foundation.
Head: cursor/v011-cache-acquire-cli-bd04 @ b09c01e0 (plus later spec-status commit on the tip only).
Folds #208 and #210. CI green. Still draft. Do not merge. Review this layer, then the stack.
