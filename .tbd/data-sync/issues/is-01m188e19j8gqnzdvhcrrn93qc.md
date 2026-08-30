---
type: is
id: is-01m188e19j8gqnzdvhcrrn93qc
title: SSE routes are exempt from parity; bounded frame capture would cover them
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/done/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
created_at: 2026-08-30T02:37:01.105Z
updated_at: 2026-08-30T02:37:01.105Z
---
/api/events and /api/stream are the parity table's only exempt rows: a server-sent-event response never terminates, so there is no envelope to pin. metab --api now bounds the request and fails with a clear message rather than hanging, which is correct but is not coverage. A stronger option: have --api detect content-type text/event-stream on http.response.start and capture a bounded number of frames or bytes, then report them. That would let a golden pin the first events a client sees and remove both exemptions. Weigh against the added surface in a mode whose value is being one simple thing.
