---
type: is
id: is-01m188e19j8gqnzdvhcrrn93qc
title: SSE routes are exempt from parity; bounded frame capture would cover them
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/done/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-08-30T02:37:01.105Z
updated_at: 2026-11-14T18:43:57.979Z
---
/api/events and /api/stream are the route-parity table's two streaming exemptions: a server-sent-event response never terminates, so there is no envelope to pin. metab --api detects text/event-stream when the response starts and fails at once with a clear message (src/metabrowser/cli/asgi_client.py:242, :301), which is correct but is not coverage. A stronger option: after that detection, capture a bounded number of frames or bytes and report them, so a golden pins the first events a client sees and both exemptions go. Weigh against the added surface in a mode whose value is being one simple thing.
