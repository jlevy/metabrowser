---
type: is
id: is-01m74wkyzy0q4g475yd1cmjat3
title: "PR #349 A7: a transient 429 switches a file to Source"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
hold: null
hold_until: null
created_at: 2026-11-11T08:47:00.093Z
updated_at: 2026-11-11T09:51:50.458Z
started_at: 2026-11-11T08:47:24.829Z
closed_at: 2026-11-11T09:51:50.457Z
close_reason: "A7 fixed in de42f53d: 429 keeps Rendered and retries with doubling backoff; in-flight requests finish instead of aborting. DOM test and headless Chrome simulation (0 files left in Source against 32)."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: diff-markdown.js:276-279, 343-366; pull_rendered_diff.py:150-157. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
