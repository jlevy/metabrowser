---
type: is
id: is-01m6th4qn5b1s27zkw8rw3736h
title: Prefetch PR details in the background when the page loads
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:14:02.404Z
updated_at: 2026-11-07T08:14:58.231Z
started_at: 2026-11-07T08:14:58.231Z
---
User observes a one-to-two-second detail fetch after clicking PRs and wants lightweight PR metadata/details prepared in the background as soon as the page loads. Trace current prefetch admission, cache reads, visible-row preparation, and click settlement; measure competing hypotheses and implement the minimal bounded scheduler/cache correction. Do not bulk fetch diffs already available through Git or trigger per-row Git acquisition. Record call counts, cache state, timing and concise automated/session/browser evidence, update design and performance notes, and install the verified build.
