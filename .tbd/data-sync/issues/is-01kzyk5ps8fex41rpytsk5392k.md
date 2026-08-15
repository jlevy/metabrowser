---
type: is
id: is-01kzyk5ps8fex41rpytsk5392k
title: Add trailing slashes to Treemap folder labels
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
created_at: 2026-08-13T22:16:36.391Z
updated_at: 2026-08-13T22:35:37.487Z
closed_at: 2026-08-13T22:35:37.487Z
close_reason: "Implemented the shared file identity SDK/CSS primitive, Files-overview and Treemap icon consumers, visual-only Treemap folder slashes, and whole-cell type-preserving hover; focused tests, make verify, live-browser validation, pre-push verification, and all PR #37 CI jobs pass."
---
Render every visible Treemap directory name with a trailing slash while leaving file labels unchanged. Keep accessible names explicit about folder versus file and preserve navigation paths without a synthetic slash.
