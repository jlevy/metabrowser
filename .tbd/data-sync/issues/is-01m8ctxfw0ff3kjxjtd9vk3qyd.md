---
type: is
id: is-01m8ctxfw0ff3kjxjtd9vk3qyd
title: Use the core renderer for Markdown frontmatter and code excerpts
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-structured-data-views.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/913
    at: 2026-11-27T09:59:03.579Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8ctvgrty5asxe2xh62gzn8v
hold: null
hold_until: null
created_at: 2026-11-26T21:06:52.415Z
updated_at: 2026-11-27T09:59:03.580Z
started_at: 2026-11-26T21:40:41.544Z
---
Recognize fenced JSON and YAML frontmatter in KPress, preserve original bytes and placement, and lazily mount the same controls for both formats and their code fences.

## Notes

Frontmatter and eligible top-level YAML and JSON Markdown fences use the same lazy Table, Tree and Source renderer. Fence markers match original file revision, line, language and content. Chrome tested independent disclosures, color from the shared syntax service, inline branches and original Source bytes. Browserless UI and API goldens cover both embeddings. Full cross-repository verification remains gated by the published SoftSchema collection release.
