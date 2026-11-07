---
type: is
id: is-01m6th4qn5b1s27zkw8rw3736h
title: Prefetch PR details in the background when the page loads
kind: bug
status: in_progress
priority: 1
version: 7
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6tv7ag6nfbnhhm12xexrwyy
  - is-01m6tz4mcm7zgwd85mrhs1cpmc
hold: null
hold_until: null
created_at: 2026-11-07T08:14:02.404Z
updated_at: 2026-11-07T12:18:39.123Z
started_at: 2026-11-07T08:14:58.231Z
---
User observes a one-to-two-second detail fetch after clicking PRs and wants lightweight PR metadata/details prepared in the background as soon as the page loads. Trace current prefetch admission, cache reads, visible-row preparation, and click settlement; measure competing hypotheses and implement the minimal bounded scheduler/cache correction. Do not bulk fetch diffs already available through Git or trigger per-row Git acquisition. Record call counts, cache state, timing and concise automated/session/browser evidence, update design and performance notes, and install the verified build.

## Notes

Final scheduler2fc is independently reviewed and integrated. Exp055/H84 accepts only the observed metadata-readiness result: six alternating pairs for public pull request310, the twelfth Open row, measured71–80ms versus1123–3357ms from driver click to visible exact description. No full record existed before any click. Added GraphQL work, unknown uninstrumented costs, and unequal footprint windows are reported. Startup and full-record ranges overlap; no paint, INP, universal startup, or full Conversation speed claim. Production sessions cover viewport/catalog traversal, prolonged contention, reconnect, Open-first priority, and identity replacement. Final full gate, publication, and CI are pending.

Acceptance clarified: actual viewport and scrolling define priority demand, followed by progressive warming of remaining available PR metadata. Eight may bound one transport batch, never which PRs are prepared; no finite retry count may abandon still-current demand. Cached lightweight descriptions survive cohort changes and 60-second freshness expiry via mb-eicc. Failures/rate holds pause work; normal reconnection/reload/epoch recovery resumes. H84/exp-055 owns before/after evidence and distinguishes deterministic session timings from real browser/provider timings.
