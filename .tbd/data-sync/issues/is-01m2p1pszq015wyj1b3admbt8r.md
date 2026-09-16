---
type: is
id: is-01m2p1pszq015wyj1b3admbt8r
title: "Repository source boundary review: publish content-source PR"
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
created_at: 2026-09-16T21:24:32.374Z
updated_at: 2026-09-16T21:24:54.998Z
started_at: 2026-09-16T21:24:54.997Z
---
Independently review RepositorySubject, ContentSource, AttachedFilesystemSubject, source capabilities, one-active-subject lifecycle, filesystem-only plugin API gating, route/inventory generalization, exact-root containment, CLI parity, and goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green acquisition head. Record exact stack evidence and final green CI. Do not merge.
