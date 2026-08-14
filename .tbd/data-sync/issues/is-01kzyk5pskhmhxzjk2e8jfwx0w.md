---
type: is
id: is-01kzyk5pskhmhxzjk2e8jfwx0w
title: Unify Treemap cell hover without text-only highlighting
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - folder-treemap
  - pr-37
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T22:16:36.402Z
updated_at: 2026-08-13T22:35:37.473Z
closed_at: 2026-08-13T22:35:37.473Z
close_reason: "Implemented the shared file identity SDK/CSS primitive, Files-overview and Treemap icon consumers, visual-only Treemap folder slashes, and whole-cell type-preserving hover; focused tests, make verify, live-browser validation, pre-push verification, and all PR #37 CI jobs pass."
---
Remove the nested folder label strip hover background so the text has no separate white or local hover state. Hover should affect the whole cell only, lightening its surface and border together while preserving the resting contrast between them and without changing stacking or child visibility.
