---
type: is
id: is-01kzyk5pts2ds3822n6pq87kj2
title: Render shared file icons in Treemap cells
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - folder-treemap
  - pr-37
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T22:16:36.440Z
updated_at: 2026-08-13T22:35:37.505Z
closed_at: 2026-08-13T22:35:37.505Z
close_reason: "Implemented the shared file identity SDK/CSS primitive, Files-overview and Treemap icon consumers, visual-only Treemap folder slashes, and whole-cell type-preserving hover; focused tests, make verify, live-browser validation, pre-push verification, and all PR #37 CI jobs pass."
---
Place the canonical navigation file-type icon to the left of every visible Treemap file label, using the shared SDK helper and subtype class. Folder labels keep their trailing-slash identity and do not receive a file icon.
