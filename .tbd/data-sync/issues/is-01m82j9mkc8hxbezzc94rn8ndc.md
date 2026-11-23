---
type: is
id: is-01m82j9mkc8hxbezzc94rn8ndc
title: "Pull request head follows new pushes: the served code moves to the new head, and Changes follows with a note naming the old and new head and a way back"
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
hold: null
hold_until: null
created_at: 2026-11-22T21:23:48.935Z
updated_at: 2026-11-23T06:37:51.362Z
started_at: 2026-11-23T06:37:51.328Z
---
Decided by the owner 2026-11-22 (mb-qp3s, "Take both" in chat): under branch-follow, a pull request's head follows new pushes like a branch.

Today, on a repository URL, the served code stays on the head the pull request had until **Switch to the head**, and Changes keeps its diff with "New commits were pushed; updating." and **Show the newer changes** (docs/reviewing-pull-requests.md; pull-page.js). With the probes (mb-sjgl, under mb-dip2) a push reaches the page within seconds, so these offers now appear seconds after every push during a review.

Target:
- **Served code:** a pin served under `refs/pull/<n>/head` follows when a pull request refresh moves that ref, as a branch pin does (`follows_moves` and `_FOLLOWED_REF_PREFIXES` in mirror_refresh.py, MirrorSession.observe). **Switch to the head** goes away for that case; a commit opened by its ID still stays put.
- **Changes:** shows the new head's diff, with a one-line note naming the old and new head and a way back to the old diff. Keep the reader's file and scroll where the file still exists, as a followed branch keeps line and scroll.
- Beside a checkout (no pin), only Changes is affected.

Update in the same change: docs/reviewing-pull-requests.md (Browse code row and the Changes text), arch-mirror-acquisition-and-refresh.md Following a Branch ("A pull request's head does not follow yet, which waits on bead mb-qp3s"), the comment above `_FOLLOWED_REF_PREFIXES` in mirror_refresh.py, a changelog.d fragment, and the page session goldens and parity rows.
