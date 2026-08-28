---
type: is
id: is-01m134g4fpngm8spx6tp1y3mz9
title: "D5: the scroll-origin section argues from a falsified premise"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/reviews/review-2026-08-27-independent-design-review.md
labels: []
dependencies: []
parent_id: is-01m134g1jm1dr1xgfhct0ja3c7
created_at: 2026-08-28T02:52:03.445Z
updated_at: 2026-08-28T03:02:50.610Z
closed_at: 2026-08-28T03:02:50.609Z
close_reason: Fixed in dbd5521 (D5). See the commit message and the plan diff.
resolution: null
duplicate_of: null
---
plan-2026-08-26 lines 300-303 declare 'not acceptable ... one scroller with an offset correction applied at the call site', which is exactly what shipped in 0715a66 as historyOrigin(). The section must be re-derived against the code: the surviving argument for separate scrollers is UX, not correctness, and the plan currently forbids the implementation.
