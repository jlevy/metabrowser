---
type: is
id: is-01m0w539fx31x7vj0rv24twqmm
title: Implement bounded revision preparation and atomic handoff
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w53j45t8y2p1w9kka5b9t7
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:47:50.140Z
updated_at: 2026-08-25T10:34:41.383Z
closed_at: 2026-08-25T10:07:30.725Z
close_reason: Implemented in-flight detail sharing, bounded pointer/focus comparison preparation, concurrent detail/assets/comparison work, prepared diff rendering through ctx.raw, atomic staged preview replacement, stale-claim safety, exact disposal, performance labels, and focused tests. make verify passes.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/git-panel.js fetchCommitDetail, beginDiffPreparation, prepareRevision, cancelSpeculativePreparation, clearPendingState, afterNextPaint, selectCommit, renderCommitDetail, mountCommitDiff, and disposeCommitDiff; src/metabrowser/static/app.js renderPreviewNode and renderPreviewHtml transient-state cleanup; src/metabrowser/static/types.d.ts MetabrowserShellRuntime; src/metabrowser/builtin_plugins/diff/index.js view.render prepared ctx.raw path; tests/dom/git-panel-behavior.js; tests/test_browser_loading_delay.py. Behavior/invariants: share in-flight detail; start detail/assets/comparison concurrently; retain one replaceable abortable speculative comparison; reuse matching preparation; keep the prior preview and diff alive until a detached replacement mounts; enforce exact revision and preview claim at every await; dispose stale and replaced handles exactly once; direct diff views still fetch; no public SDK, server route, dependency, or compatibility layer change. Acceptance: tests cover concurrency, duplicate suppression, slot replacement and abort, routes, errors, stale races, atomic continuity, disposal, and finite performance labels.
