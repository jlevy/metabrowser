---
type: is
id: is-01m0w539fx31x7vj0rv24twqmm
title: Implement bounded revision preparation and atomic handoff
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w53j45t8y2p1w9kka5b9t7
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:47:50.140Z
updated_at: 2026-08-25T10:07:30.725Z
closed_at: 2026-08-25T10:07:30.725Z
close_reason: Implemented in-flight detail sharing, bounded pointer/focus comparison preparation, concurrent detail/assets/comparison work, prepared diff rendering through ctx.raw, atomic staged preview replacement, stale-claim safety, exact disposal, performance labels, and focused tests. make verify passes.
resolution: null
duplicate_of: null
---
Files/functions: tests/dom/git-panel-behavior.js; tests/test_git_browser_js.py if wrapper coverage changes; src/metabrowser/static/git-panel.js fetchCommitDetail, scheduleHover, selectCommit, renderCommitDetail, mountCommitDiff, disposeCommitDiff and new preparation/pending helpers; src/metabrowser/builtin_plugins/diff/index.js view.render; src/metabrowser/static/types.d.ts only if the existing raw contract needs a narrower checked-JS annotation. Behavior/invariants: share in-flight commit detail; start detail, ensureKindAssets, and comparison hook concurrently; store at most one replaceable/abortable speculative comparison; pointer/focus intent starts preparation without waiting for hover text; selection consumes prepared data and passes it through ctx.raw; direct diff views still fetch; keep old preview and diff alive until replacement, then dispose exactly once; selected revision/claim wins across every await; failure is explicit; no new public SDK or dependency. Acceptance: focused tests are written failing first and cover duplicate suppression, concurrency, single-slot replacement, stale selection, route behavior, error behavior, and disposal; exact text/diff state and rapid selections remain correct; perf.measureAsync labels cover data/assets/mount/ready phases.
