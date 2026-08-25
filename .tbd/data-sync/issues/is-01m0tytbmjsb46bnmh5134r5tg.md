---
type: is
id: is-01m0tytbmjsb46bnmh5134r5tg
title: "Monitor PR #74 and FDU #44/#47 alignment through adoption readiness"
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-08-24T22:38:51.537Z
updated_at: 2026-08-25T00:53:29.409Z
---
Recurring alignment owner for MetaBrowser PR #74 and FDU PRs #44 and #47. Each cycle must sync both tbd stores, inspect exact PR heads, CI, issue comments, formal reviews, inline threads, and current FDU implementation beads, then review material FDU deltas against the implemented InventoryHandle contract and performance/adoption gates. Actionable MetaBrowser feedback is addressed through per-finding beads and a disposition map; FDU defects or drift are deduplicated into fdu-u7vo and published on the appropriate FDU PR. Report only material changes and keep monitoring until the three PRs and adoption handoff reach a terminal state.

## Notes

MONITOR BASELINE (2026-08-24). MetaBrowser PR #74 head 68eeaac: all five CI jobs green; no unaddressed issue comments, formal reviews, or inline comments; review response at issuecomment-5402554680. FDU PR #44 head 7f18f20: all 19 checks green; final design update at issuecomment-5402597348. FDU PR #47 head a3960fb: all 19 checks green; exact-head review at issuecomment-5402590823. Existing FDU owners were updated and synced: fdu-5yqb reopened; fdu-91ru, fdu-kbir, fdu-fltq, fdu-vfyw, and fdu-u7vo extended. Hourly heartbeat monitor is active; on any new head, diff before commenting and preserve exact-head attribution.

FIRST MONITOR DELTA (2026-08-24). FDU #47 advanced from a3960fb to 558461a after the baseline review. All 19 checks remained green. Exact diff review found the carrier's terminal cursor is sampled after apply_next under a separate guard, async teardown can deadlock with run_coroutine_threadsafe handoff and stall the event loop until its five-second join timeout, and state/work remain absent. fdu-vfx7 was reopened; fdu-jxs0, fdu-fltq, and fdu-u7vo were updated; formal review pullrequestreview-5013380346 posted. MetaBrowser PR #74 cross-link comment was edited to current status, and FDU document links now follow #47's active branch instead of a stale commit pin.

SECOND MONITOR DELTA (2026-08-24). FDU #47 advanced from 558461a to 56dcf56; all 19 checks remained green and mergeability stayed clean. Exact diff review accepted fdu-662n and fdu-g0n4 (positive page limits and native max_size), and fdu-hfdw (filtered report visit accounting). The GIL detach and exact-or-absent CPU direction in fdu-kbir are correct, but its full-boundary gate was reopened: conversion_ns stops before projection dictionaries and omits public Python Bundle/model conversion; materialized_bytes is an incomplete second O(output) estimate; the public concurrency test would pass under GIL serialization. fdu-kbir and fdu-u7vo were updated and synced; formal review pullrequestreview-5013619647 posted. MetaBrowser PR #74 remains at 68eeaac with five green checks and no new feedback; FDU #44 remains at 7f18f20 with 19 green checks. Existing P1 adoption blockers fdu-vfx7 and fdu-91ru, plus fdu-jxs0/fdu-fltq and the remaining acceptance graph, remain open.

THIRD MONITOR DELTA (2026-08-25). FDU #47 advanced from 56dcf56 to exact head 715f748. The review accepted removal of WatcherGap from coverage (fdu-5yqb closed), actual read-side GIL detachment, exact-or-absent CPU, and moving the async join off the event loop. Three P1 blockers remain: the WatchBatch cursor can skip a direct producer commit interleaved between separately flushed watcher/reconcile deltas; long watch intervals let async teardown return after its five-second join timeout with a live worker; and the performance envelope double-counts conversion in model_ns, conflates total-boundary and projection-native Work semantics, and incompletely accounts binding payload. The timing-based GIL proof also fails the required macOS/Python 3.14 wheel job (0.0070s below its 0.0080s threshold), leaving #47 UNSTABLE with 18 green checks and one failure. fdu-vfx7 and fdu-u7vo were extended, fdu-kbir reopened, and exact-head formal review https://github.com/jlevy/fdu/pull/47#pullrequestreview-5013959124 was posted. fdu-91ru, fdu-jxs0, and fdu-fltq remain open. MetaBrowser #74 remains at 68eeaac with five green checks/no new feedback; FDU #44 remains at 7f18f20 with 19 green checks/no new feedback.
