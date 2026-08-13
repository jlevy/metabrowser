---
type: is
id: is-01kzyk58k745ke2y0qgm5vvzcy
title: Expose shared file identity icons through the browser SDK
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - design-system
  - pr-37
dependencies:
  - type: blocks
    target: is-01kzyk5psyy2vgwytahk1xn4vj
  - type: blocks
    target: is-01kzyk5pts2ds3822n6pq87kj2
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T22:16:21.858Z
updated_at: 2026-08-13T22:35:37.456Z
closed_at: 2026-08-13T22:35:37.455Z
close_reason: "Implemented the shared file identity SDK/CSS primitive, Files-overview and Treemap icon consumers, visual-only Treemap folder slashes, and whole-cell type-preserving hover; focused tests, make verify, live-browser validation, pre-push verification, and all PR #37 CI jobs pass."
---
Add one public window.metabrowser helper and one shared CSS alignment primitive that resolve the same file-type SVG and subtype class used by navigation. Document and type the API so plugin views can place a canonical file or extension icon to the left of a label without reaching into app.js globals.
