---
type: is
id: is-01m1cd5xpx3jtrmy3rvdt5q2qq
title: "PR #90 PLAN-06: Phase 2's premise is false: transcripts are normalized, not raw responses"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1cd5vdf1q8c3mj15at60znc
created_at: 2026-08-31T17:16:55.900Z
updated_at: 2026-08-31T17:16:55.900Z
---
"A transcript already holds a real response" is wrong. Goldens carry type-changing placeholders and elisions inside JSON strings, so validating them against a schema needs a stated mechanism the plan does not choose.
