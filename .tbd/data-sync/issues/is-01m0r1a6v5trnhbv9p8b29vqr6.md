---
type: is
id: is-01m0r1a6v5trnhbv9p8b29vqr6
title: "PR #73 review R2: remove refuted interaction-latency detector"
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0r191gatek6ffx1e50wmgr8
created_at: 2026-08-23T19:24:44.773Z
updated_at: 2026-08-23T19:25:09.248Z
---
PR #73. devtools/check_interaction_latency.py:1 contradicts the PR body by asserting connection starvation after that mechanism was refuted. Delete it; add a guard only after root-cause attribution. Review: https://github.com/jlevy/metabrowser/pull/73#pullrequestreview-5003175212
