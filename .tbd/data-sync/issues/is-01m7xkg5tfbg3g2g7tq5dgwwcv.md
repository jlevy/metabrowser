---
type: is
id: is-01m7xkg5tfbg3g2g7tq5dgwwcv
title: Join an in-progress Markdown worker replacement before closing the event loop
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-20T23:08:39.630Z
updated_at: 2026-11-20T23:08:46.715Z
started_at: 2026-11-20T23:08:46.714Z
---
Metabrowser #674 CI run 44833276784 job 136623476652 on Linux CPython 3.12.13, synthetic merge 1a26a9658, returned the expected render_deadline HTTP 422 for tests/golden/cli-api-untrusted-markdown.tryscript.md, then printed asyncio’s closed-loop warning for pid 5731. The worker blob and lifespan shutdown match current main; prior fix 075f8bd45 handles published children. A deadline starts a replacement, but shutdown cancels and drops a startup task before waiting only for published processes. If the replacement spawned before create_subprocess_exec finished, asyncio.run can cancel its cleanup a second time before the child watcher delivers the exit. Join the current loop’s cancelled start within the existing bounded reaping window, and cover the pre-publication case deterministically. Keep the deadline/refusal/golden behavior. Related: mb-644p and mb-p9i5.
