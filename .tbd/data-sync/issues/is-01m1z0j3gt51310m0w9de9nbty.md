---
type: is
id: is-01m1z0j3gt51310m0w9de9nbty
title: Reproduce the activity overlay version race from full verification
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T22:41:57.785Z
updated_at: 2026-09-08T00:02:46.975Z
closed_at: 2026-09-08T00:02:46.972Z
close_reason: The overlay-only transition test now disables native observation so it verifies its intended engine-version invariant deterministically. Separate watcher tests remain enabled. Full pytest run passes 1893 tests.
resolution: null
duplicate_of: null
---
Baseline make verify at 7190f21f failed test_quiet_overlay_transition_preserves_engine_version_and_pid_label: engine sequence advanced 523 to 528 between the activity refresh and quiet polls. Targeted suite passed. Investigate delayed duplicate watcher observations and unchanged refresh version churn; keep regression coverage deterministic.
