---
type: is
id: is-01m0c4czd01fxz2rv1na9s3b5q
title: Wire the diff file kind and comparison view descriptors into the shell
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4dfp54t81297rz61cse4r
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:47.999Z
updated_at: 2026-08-19T04:28:18.253Z
---
Phase 1 half: classify .diff and .patch as the diff kind so opening one routes through the existing file-preview path with no new surface, with Diff as the default view. Phase 2 half: inject comparison views into changed files' descriptors in comparison context, Diff as context default and After beside it, selection flowing through navigateToPath and preferredViewId — later presentations are additional tabs from the same layout.
