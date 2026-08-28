---
type: is
id: is-01m134g66zcjggm18j8tdsbgp1
title: "D8: Git-status Phase 0 promises measurements only later phases can produce"
kind: chore
status: closed
priority: 2
version: 2
spec_path: docs/project/reviews/review-2026-08-27-independent-design-review.md
labels: []
dependencies: []
parent_id: is-01m134g1jm1dr1xgfhct0ja3c7
created_at: 2026-08-28T02:52:05.211Z
updated_at: 2026-08-28T03:02:51.517Z
closed_at: 2026-08-28T03:02:51.516Z
close_reason: Fixed in dbd5521 (D8). See the commit message and the plan diff.
resolution: null
duplicate_of: null
---
Phase 0 says it produces no code, yet its measurement list includes peak retained parser memory and browser time-to-first-row and DOM cost, which require the Phase 1 parser and the Phase 2 panel. Split the list: corpus plus command-level status/diff latency and bytes in Phase 0; retained-memory and browser costs recorded during Phase 1 and 2 against the same corpus.
