---
type: is
id: is-01m7bmkrjssbj4q2k7wrh3t2zz
title: "Pulls core prefetch: a slow batch stalls the walk forever, and visible requests wait behind it"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T23:41:45.944Z
updated_at: 2026-11-14T01:04:07.121Z
closed_at: 2026-11-14T01:04:07.119Z
close_reason: "Merged in #414: lane timeouts (visible 10 s, background 30 s), visible demand aborts background, a batch unanswered twice is passed over with per-batch 30 s deadlines, teardown aborts pending prepares, and the prepare handler stops when its client leaves (499). Follow-up: mb-2j4h."
resolution: null
duplicate_of: null
---
Found while investigating mb-yhvu (#412). In `pulls-panel.js`, every pull-cores-prepare request aborts at `CORE_CONTROL_TIMEOUT_MS = 2000` (the same 2 s as the server's slow-request log), and the background walk retries the same batch indefinitely (1, 2, 4, 8, 16 s, then every 30 s) because `warmAfter` advances only on a ready answer. A visible-lane request made while a background one is in flight waits behind it. Reproduced in the production controller (virtual time): a batch that always times out was asked for at 3, 4, 6, 10, 18, 34, 64, 94, 124, 154 s and the walk never moved past it.

Done when: a slow or failing batch cannot stall the walk forever (skip or give up after a bound, measured), a visible demand is not stuck behind a background request (abort it or run it in its own lane), and the timeout is chosen from measurement rather than equal to the log threshold; pinned in the prefetch session.
