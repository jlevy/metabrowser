---
type: is
id: is-01m6mwaa51n75m8kxnprppnr6n
title: Cancel Git preparation and deferred hydration when another preview takes ownership
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T03:33:52.928Z
updated_at: 2026-11-05T03:33:53.580Z
started_at: 2026-11-05T03:33:53.579Z
---
Actual production-module reproduction found two cross-owner cancellation failures: Git comparison preparation stays un-aborted after a file claim and completes successfully after ownership changed; a rendered diff hydration scheduler continues its active response and starts queued old-file work after a PR claim. Stale DOM rendering is guarded, but obsolete work still consumes resources. Expose a narrow internal GitPanel.cancelPending that stops hover/pending work, aborts and clears preparation, and calls the diff handle cancellation without disposing retained DOM or history. Call it for non-Git preview claims. Preserve same-revision return, prior useful content and new-owner readiness; pin real AbortSignals, zero successful old work/queued starts and exact app claim wiring using existing focused sessions. No new public SDK or generic event framework. Root evidence: isolated exact-source production probe, no browser/network or product mutation during reproduction. Candidate verification and whole-journey measurements pending.
