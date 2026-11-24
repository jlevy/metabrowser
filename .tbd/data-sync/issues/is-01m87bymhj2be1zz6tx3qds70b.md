---
type: is
id: is-01m87bymhj2be1zz6tx3qds70b
title: "PR #771 A1: the projection reads a kept raw checkbox as dropped, so it and its tick are source_only"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:09.164Z
updated_at: 2026-11-24T18:30:09.939Z
started_at: 2026-11-24T18:09:33.875Z
closed_at: 2026-11-24T18:30:09.933Z
close_reason: "Fixed in 7731d0cc8: _RawMarkup reads an input through allowed_attributes as an image is read (an input it keeps nothing of is read as before), and reads a duplicated attribute as its first. Confirmed by test_a_raw_checkbox_and_its_tick_are_changes_the_render_shows (4 cases fail before, pass after) and test_a_raw_input_the_render_drops_is_flagged."
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/diff/markdown_projection.py:672 (_RawMarkup.handle_starttag): every tag outside ALLOWED_TAGS but img goes down the dropped path, though the allowlist keeps a raw <input type=checkbox>. A raw table-cell checkbox added or ticked is flagged source_only. Fix: route input through allowed_attributes as img is; tests for added/ticked/unticked raw box (not source_only) and raw text input (source_only). PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
