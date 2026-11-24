---
type: is
id: is-01m87bymhj2be1zz6tx3qds70b
title: "PR #771 A1: the projection reads a kept raw checkbox as dropped, so it and its tick are source_only"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:09.164Z
updated_at: 2026-11-24T18:09:33.877Z
started_at: 2026-11-24T18:09:33.875Z
---
Medium. src/metabrowser/diff/markdown_projection.py:672 (_RawMarkup.handle_starttag): every tag outside ALLOWED_TAGS but img goes down the dropped path, though the allowlist keeps a raw <input type=checkbox>. A raw table-cell checkbox added or ticked is flagged source_only. Fix: route input through allowed_attributes as img is; tests for added/ticked/unticked raw box (not source_only) and raw text input (source_only). PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
