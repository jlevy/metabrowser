---
type: is
id: is-01m8cetvphmzwwprcqx5hde0gr
title: Make the macOS process-group test wait for a live fixture
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/890
    at: 2026-11-26T19:28:55.748Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T17:35:43.309Z
updated_at: 2026-11-26T19:35:00.795Z
started_at: 2026-11-26T19:19:19.738Z
closed_at: 2026-11-26T19:35:00.795Z
close_reason: "Fixed in PR #890. All 49 focused tests and all 65 native macOS tests passed. Hosted CI passed at the PR head."
resolution: null
duplicate_of: null
---
The macOS tier can time out before test_a_live_group_is_stopped_without_reading_the_process_table starts its child. It passed by itself and failed during full-tier runs with no child.pid, so those failures never exercised shutdown of a live group. Separate fixture readiness from the shutdown check, preserve the assertion that teardown never reads the process table, and verify the case by itself and in the native tier. Observed while validating PR #380.
