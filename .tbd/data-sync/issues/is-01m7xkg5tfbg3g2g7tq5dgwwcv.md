---
type: is
id: is-01m7xkg5tfbg3g2g7tq5dgwwcv
title: Join an in-progress Markdown worker replacement before closing the event loop
kind: bug
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/680
    at: 2026-11-20T23:11:39.345Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-20T23:08:39.630Z
updated_at: 2026-11-20T23:24:03.656Z
started_at: 2026-11-20T23:08:46.714Z
closed_at: 2026-11-20T23:24:03.655Z
close_reason: "PR #680 merged as 83a71ccd0fcfbf726d2294ea110a0bf28353f670 after exact-head review and passing PR CI run 44834917928 attempt 2. Linux Python 3.12 passed the previously failing Markdown golden. The confirmed fix joins replacement startup cancellation inside the existing shutdown budget. Post-merge main run 44836399377 is tracked separately."
resolution: null
duplicate_of: null
---
Metabrowser #674 CI run 44833276784 job 136623476652 on Linux CPython 3.12.13, synthetic merge 1a26a9658, returned the expected render_deadline HTTP 422 for tests/golden/cli-api-untrusted-markdown.tryscript.md, then printed asyncio’s closed-loop warning for pid 5731. The worker blob and lifespan shutdown match current main; prior fix 075f8bd45 handles published children. A deadline starts a replacement, but shutdown cancels and drops a startup task before waiting only for published processes. If the replacement spawned before create_subprocess_exec finished, asyncio.run can cancel its cleanup a second time before the child watcher delivers the exit. Join the current loop’s cancelled start within the existing bounded reaping window, and cover the pre-publication case deterministically. Keep the deadline/refusal/golden behavior. Related: mb-644p and mb-p9i5.

## Notes

Independent Codex review of PR #680 at a2f3d70cde5c400fa379aa692f1b4d37c0284e02: joining the cancelled launch inside the existing two-second reaping budget is narrow and preserves caller cancellation. The regression pauses the replacement with an event before its Process is published, then asserts its cancellation cleanup has finished when aclose returns. Only the worker and its regression test changed. Branch contains current main a1ccf1cc14af75a5bcaa906cf3e7fe3d44d9963c. CI run 44834917928 is the executable validation.

PR CI run 44834917928 attempt 2 passed all applicable checks on the reviewed head (27 passed plus the conditional stack skip). Linux 3.12 golden job 136628750821 explicitly passed the former failure. The first attempt had a separate nested pytest timing failure, tracked and green on a single retry in mb-05e5.
