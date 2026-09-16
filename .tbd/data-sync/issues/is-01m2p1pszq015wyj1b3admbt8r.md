---
type: is
id: is-01m2p1pszq015wyj1b3admbt8r
title: "Repository source boundary review: publish content-source PR"
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m0dkj0gqvpzpxm7t1tpshf30
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:32.374Z
updated_at: 2026-09-16T21:27:34.760Z
started_at: 2026-09-16T21:24:54.997Z
---
Independently review RepositorySubject, ContentSource, AttachedFilesystemSubject, source capabilities, one-active-subject lifecycle, filesystem-only plugin API gating, route/inventory generalization, exact-root containment, CLI parity, and goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green acquisition head. Record exact stack evidence and final green CI. Do not merge.
