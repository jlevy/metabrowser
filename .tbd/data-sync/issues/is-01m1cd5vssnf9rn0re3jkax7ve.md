---
type: is
id: is-01m1cd5vssnf9rn0re3jkax7ve
title: "PR #90 PLAN-01: Schema plan's coverage premise fails: most surfaces have no TypedDict"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1cd5vdf1q8c3mj15at60znc
created_at: 2026-08-31T17:16:53.944Z
updated_at: 2026-08-31T17:16:53.944Z
---
Only tree, rollup, and git envelopes have TypedDicts. /api/file -- the plan's own opening example -- has none, and most of the 26 covered surfaces have none. No phase authors them, so Phase 2's "every existing transcript" is unachievable and Phase 4 would strip prose with nothing to replace it.
