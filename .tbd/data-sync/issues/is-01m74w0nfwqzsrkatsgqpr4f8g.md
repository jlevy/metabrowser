---
type: is
id: is-01m74w0nfwqzsrkatsgqpr4f8g
title: "PR #348 A3: prepare_comparison action and preparing_comparison field lack golden and route-map entry"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:27.771Z
updated_at: 2026-11-11T10:57:50.641Z
started_at: 2026-11-11T09:24:55.866Z
closed_at: 2026-11-11T10:57:50.640Z
close_reason: "Fixed: 7c927a87 (cli-github-checkout-idle.txt pins not_due without a store, a wrong revision, the started request with preparing_comparison: true, a repeat, and the reader's Changes), 9163be07 + 868fce7d (route map documents both names; the idle session has its own parity row, the pull-refresh row names the golden)."
resolution: null
duplicate_of: null
---
Medium. pull_route.py:118, 406-407, 559-573, 611-634; arch-views-models-routes.md:226-236, parity row line 724. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
