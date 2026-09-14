---
type: is
id: is-01m2fcz8t86c9g684tt6dkfgg0
title: "PR #118 review R1: file header and diff file bar two-size rows do not share a baseline"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcz83jz15cmfj6yfdvm1sq
created_at: 2026-09-14T07:26:43.014Z
updated_at: 2026-09-14T07:26:52.087Z
---
PR #118 review R1 (Medium). docs/design-system.md:639-645 states the baseline rule universally, but .file-header (13px path vs 12px size, measured -0.75px) and .diff-file-toggle (13px .diff-file-path vs 12px .diff-file-note, builtin_plugins/diff/styles.css:77-122) still center. Apply the same opt-in in this PR, measure before/after, extend the test, keep the doc accurate.
