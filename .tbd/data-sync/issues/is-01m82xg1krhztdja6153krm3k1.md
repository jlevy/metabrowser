---
type: is
id: is-01m82xg1krhztdja6153krm3k1
title: "PR #696 A4: below the floor the plan stops the visible page updating; owner chose: on-screen changes still read"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82xey0wss692acqkvv0yv31
created_at: 2026-11-23T00:39:33.231Z
updated_at: 2026-11-23T00:39:33.231Z
---
Medium. plan:228-229, 237-245. Owner decision 2026-11-22: below BACKGROUND_FLOOR, a change a probe finds on the visible page still starts its full read; the FULL_REFRESH_S read and background/prefetch work stop. https://github.com/jlevy/metabrowser/pull/696#pullrequestreview-6015381056
