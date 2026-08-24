---
type: is
id: is-01m0tz5xddw360nz6p59h5g00v
title: "Step 5: Integrate hydration, scheduling, folds, and disposal"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz6g44qzh76psm0gg91ays
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:45:10.188Z
updated_at: 2026-08-24T22:45:29.347Z
---
Files and functions: src/metabrowser/builtin_plugins/diff/diff-view.js setChangeLoader, hydrateDeferred, createFileState, scheduleSyntaxEnhancement, renderFileSection, mountDiffView, renderFoldControl; src/metabrowser/builtin_plugins/diff/index.js deferred comparison loader; tests/dom/diff-view-behavior.js. Behavior: cache each ready or hydrated patch in file state, enhance files sequentially in document order with an event-loop yield between files, use one mount AbortController for asset waits and deferred fetches, guard every late continuation with the mount generation, and count split changed-run folds as max(deletions, additions) with a stable file/hunk/run key. Invariants: switching layout never restarts hydration or syntax; collapse/fold state survives reprojection; dispose aborts waits/fetches, clears timers/listeners, and forbids detached DOM mutation or unhandled rejections; one file failure does not block later files. TDD acceptance: deferred load receives signal and hydrates once, switching during pending work stays stable, unequal split runs hide the same paired interval, many ready files visibly yield between units, one failed file continues the queue, and disposal before fetch/token completion causes no late work.
