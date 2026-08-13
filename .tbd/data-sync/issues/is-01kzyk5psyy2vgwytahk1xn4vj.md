---
type: is
id: is-01kzyk5psyy2vgwytahk1xn4vj
title: Render shared file-type icons in the Files overview
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - folder-overview
  - pr-37
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T22:16:36.413Z
updated_at: 2026-08-13T22:35:37.520Z
closed_at: 2026-08-13T22:35:37.520Z
close_reason: "Implemented the shared file identity SDK/CSS primitive, Files-overview and Treemap icon consumers, visual-only Treemap folder slashes, and whole-cell type-preserving hover; focused tests, make verify, live-browser validation, pre-push verification, and all PR #37 CI jobs pass."
---
Place the canonical navigation file-type icon to the left of every exact extension row in the Files overview. Use the shared SDK helper and alignment primitive; aggregate Total, Ignored, Remaining types, and no-extension rows remain text-only because they do not identify one file type.
