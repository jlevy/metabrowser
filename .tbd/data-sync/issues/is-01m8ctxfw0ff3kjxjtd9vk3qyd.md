---
type: is
id: is-01m8ctxfw0ff3kjxjtd9vk3qyd
title: Use the core renderer for Markdown frontmatter and code excerpts
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-structured-data-views.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8ctvgrty5asxe2xh62gzn8v
hold: null
hold_until: null
created_at: 2026-11-26T21:06:52.415Z
updated_at: 2026-11-26T21:45:24.991Z
started_at: 2026-11-26T21:40:41.544Z
---
Recognize fenced JSON and YAML frontmatter in KPress, preserve original bytes and placement, and lazily mount the same controls for both formats and their code fences.

## Notes

Frontmatter is live at 6398a4c42 in trusted and inert Markdown. Chrome exercised an actual Universe record: lazy Table, nested Tree and exact Source with original line 9, then back to the same nested Table. CLI goldens cover block/flow YAML, JSON in the frontmatter fences and CRLF. Standalone Markdown code-fence excerpts remain.
