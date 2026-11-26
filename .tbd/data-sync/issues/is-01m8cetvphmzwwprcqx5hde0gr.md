---
type: is
id: is-01m8cetvphmzwwprcqx5hde0gr
title: Make the macOS process-group test wait for a live fixture
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T17:35:43.309Z
updated_at: 2026-11-26T17:35:43.309Z
---
The macOS tier can time out before test_a_live_group_is_stopped_without_reading_the_process_table starts its child. It passed by itself and failed during full-tier runs with no child.pid, so those failures never exercised shutdown of a live group. Separate fixture readiness from the shutdown check, preserve the assertion that teardown never reads the process table, and verify the case by itself and in the native tier. Observed while validating PR #380.
