---
type: is
id: is-01m76v97zdyqm00t18wecf88k6
title: "PR #362 A7: The exit-during-health-check test exits before the check starts"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:09.132Z
updated_at: 2026-11-12T03:31:53.584Z
closed_at: 2026-11-12T03:31:53.551Z
close_reason: "A7 fixed in ae805456: the test waits for the suspended probe before the exit"
resolution: null
duplicate_of: null
---
Medium finding A7 on PR #362 (apps/macos/HealthCheckTests.swift:102). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867906946
