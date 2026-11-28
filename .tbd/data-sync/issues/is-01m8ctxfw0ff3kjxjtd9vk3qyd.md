---
type: is
id: is-01m8ctxfw0ff3kjxjtd9vk3qyd
title: Use the core renderer for Markdown frontmatter and code excerpts
kind: task
status: closed
priority: 2
version: 7
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
updated_at: 2026-11-28T18:02:52.021Z
started_at: 2026-11-26T21:40:41.544Z
closed_at: 2026-11-28T18:02:52.019Z
close_reason: "The shared three-view frontmatter and standalone YAML/JSON fence UI, exact Source ranges, and browserless/Chrome evidence landed in PR #913. Post-merge main CI passed."
resolution: null
duplicate_of: null
---
Recognize fenced JSON and YAML frontmatter in KPress, preserve original bytes and placement, and lazily mount the same controls for both formats and their code fences.

## Notes

Frontmatter and eligible top-level YAML and JSON Markdown fences use the same lazy Table, Tree and Source renderer. Fence markers match original file revision, line, language and content. Chrome tested independent disclosures, color from the shared syntax service, inline branches and original Source bytes. Browserless UI and API goldens cover both embeddings.

Standalone PR #913 passes its full 43-check GitHub run with the published dependency lock. It can land independently of the SoftSchema collection rollout.
