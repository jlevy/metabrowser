---
type: is
id: is-01m0gzsgfwnvg4nqf3krady4tt
title: Surface and retry a failed filesystem watch
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-21T01:43:27.996Z
updated_at: 2026-08-21T01:43:44.189Z
---
The watcher now announces a failed watch on the event stream as a
capability.update with backends[].state = "failed", and logs it. Nothing
consumes that yet, and nothing retries.

Why it matters: the index is only current because the watch keeps it current,
and no surface downstream can tell a quiet filesystem from a dead watch.
Requests keep being answered, and /api/rollup keeps answering 304 Not Modified
-- truthfully about the index, which has stopped being about the filesystem.
Exhausting the inotify watch limit on a large tree lands exactly here, and a
100k-file tree is the design center.

Two pieces, either useful alone:

1. Show it. The shell already listens for capability.update but reads only
   index.complete. A degraded-watch indicator would let a reader tell "nothing
   is changing" from "we stopped looking".

2. Retry it. A bounded retry with backoff would recover from a transient
   backend error. Demoting from native to polling on repeated native failure is
   the natural escalation, since polling is already the correctness fallback for
   filesystems where native watches are unreliable.

Watch out for: a retry loop that reattaches to an exhausted inotify limit every
few seconds is worse than stopping, so the backoff has to be real and the give-up
state still has to be visible.

Context: docs/project/architecture/arch-state-and-delivery.md, "Why a conditional
response is safe" and "What Is Not Solved".
