---
type: is
id: is-01m715sezspp55zz5v346nrv9n
title: Design layered Git stores for cache-first PR review
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
labels: []
dependencies:
  - type: blocks
    target: is-01m715sfem46c801k52wr03qt6
created_at: 2026-11-09T22:10:19.755Z
updated_at: 2026-11-09T22:10:20.243Z
---
Keep the live Files root and local Commits history on the checkout, and give both checkout and URL-backed PR review a shared immutable Git snapshot reader. Reuse healthy managed stores, borrow eligible checkout objects, and fetch missing objects on demand or during bounded idle work. Design process and cross-process deduplication, atomic publication, route ownership, stale metadata guards, and lender repair first. Measure the selected path before widening eager preparation. Do not change the full-clone fallback policy as a side effect.
