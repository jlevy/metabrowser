---
type: is
id: is-01m715sezspp55zz5v346nrv9n
title: Design layered Git stores for cache-first PR review
kind: feature
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m715sfem46c801k52wr03qt6
  - type: blocks
    target: is-01m718rgbk80mnnjb8d4b1r4xz
child_order_hints:
  - is-01m715y0nv4hwkwvkvfze1m4r1
hold: null
hold_until: null
created_at: 2026-11-09T22:10:19.755Z
updated_at: 2026-11-09T23:02:14.117Z
started_at: 2026-11-09T22:11:54.567Z
---
Keep the live Files root and local Commits history on the checkout, and give both checkout and URL-backed PR review a shared immutable Git snapshot reader. Reuse healthy managed stores, borrow eligible checkout objects, and fetch missing objects on demand or during bounded idle work. Design process and cross-process deduplication, atomic publication, route ownership, stale metadata guards, and lender repair first. Measure the selected path before widening eager preparation. Do not change the full-clone fallback policy as a side effect.

## Notes

Design decision under review: use a Guava-style loading-cache contract as the only path for cached Git content. A caller provides an immutable key. The cache returns ready data, joins a registered load, or atomically starts the single loader. Prefetch is the same loader with lower priority. Check durable state again under existing cross-process locks, publish after validation, keep previous mutable values through refresh, and reject stale publication by generation. Cancel waiters without canceling work for other readers. Typed failures have bounded retry. Retain side-effect-free observation routes. Reference: https://guava.dev/releases/33.4.8-jre/api/docs/com/google/common/cache/LoadingCache.html.
