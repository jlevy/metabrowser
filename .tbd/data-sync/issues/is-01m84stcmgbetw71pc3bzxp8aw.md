---
type: is
id: is-01m84stcmgbetw71pc3bzxp8aw
title: "Rendered diff: show a file with a task list, its boxes' ticks as changes"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: blocked
hold_until: null
created_at: 2026-11-23T18:13:46.765Z
updated_at: 2026-11-23T21:05:22.662Z
started_at: 2026-11-23T18:26:01.829Z
---
markdown_projection.py refuses any file with a task list (task_list), because KPress writes the checkbox as raw HTML and the inert render drops its checked state. Project the checkbox as an inert element that keeps its state, and count the state in the block's signature so ticking a box is a change.

## Notes

Blocked on a KPress release that holds https://github.com/jlevy/kpress/pull/82 (head 92ef5ade476f4f8c8202514935669d9ca126645b, open, not released). Direction from the user (2026-11-23): task lists are KPress's to render natively; Metabrowser holds no task-list case in markdown_projection.py.

What #82 changes: the box is a KPress token, type `kpress_task_checkbox` (tag `input`, nesting 0, markup `[ ]`/`[x]`/`[X]`, state in `meta["checked"]`), drawn by KPress's `_render_task_checkbox` as `<input class="task-list-item-checkbox" [checked="checked"] disabled="disabled" type="checkbox">`, in both trust modes; `list_item_open` carries `class="kpress-task task-list-item"` on the token (the `_postprocess_tasks` string replace is gone); the sanitizer keeps `input` only as a disabled checkbox.

Until then (mb-4bsb, PR stacked on #759): the box is raw HTML the inert allowlist drops, so a task list renders without its boxes, as the Document view of an untrusted document does, and a tick is a source-only change. The `task_list` refusal is gone.

Metabrowser once the release is in: pin the new kpress in pyproject.toml and uv.lock; keep a disabled checkbox and its `checked` in the inert allowlist (inert_html.py, static/inert-html.js, static/types.d.ts) so the Document view and Rendered draw the box; in markdown_projection.py count a `kpress_task_checkbox` token as one rendered element, so the box is part of the block's shape and a tick is a change; decide how KPress-owned task classes on token attrs read in the hidden signature (today any class attr is concealed attribute syntax). The earlier Metabrowser-only draft (raw HTML matching) is kept as local branch wip/mb-rm6u-task-lists (c0325141c); its allowlist, inert-html session and golden changes can be reused.
