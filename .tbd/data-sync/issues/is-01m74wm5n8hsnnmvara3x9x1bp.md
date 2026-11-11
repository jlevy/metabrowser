---
type: is
id: is-01m74wm5n8hsnnmvara3x9x1bp
title: "PR #349 C4: Rendered views arrive one at a time behind a lookahead shorter than a projection"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
hold: null
hold_until: null
created_at: 2026-11-11T08:47:06.919Z
updated_at: 2026-11-11T12:33:49.002Z
started_at: 2026-11-11T08:47:27.312Z
closed_at: 2026-11-11T12:33:49.001Z
close_reason: "C4 fixed in de42f53d and c448aae8: one-viewport lookahead (measured), first-screen projections prefetched from Conversation, one request at a time matching the server's one slot."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855871513. References: diff-markdown.js:272-290; diff-view.js:194, 2697. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).

## Notes

Phase 1 (de42f53d): own one-viewport lookahead measured; client concurrency matches the server's one slot. Open for phase 2: server prefetch of the first screen's projections when the comparison is served (github/sidekick.py, owned by #347's agent until merged forward).
