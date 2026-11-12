---
type: is
id: is-01m77fa9efyn19ckc7n6m8teg2
title: "Review G2 on #363: a second signal, or one during the run's cleanup, exits before cleanup finishes"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:52:14.926Z
updated_at: 2026-11-12T08:54:59.040Z
started_at: 2026-11-12T08:52:26.400Z
closed_at: 2026-11-12T08:54:59.039Z
close_reason: "Fixed in 4bdb8815 (#363): Cleanup.run() shares one in-flight run, and a later signal or error waits for it and keeps the first status; processes.test.mjs covers concurrent runs, two SIGTERMs, and a SIGTERM during the run's own cleanup."
resolution: null
duplicate_of: null
---
cleanUpBeforeExit called process.exit() on a second signal or error while the first was still between SIGTERM and SIGKILL for a resistant child, and Cleanup.run() popped a step before awaiting it, so a concurrent second run finished early. Share one in-flight run, and have a later signal wait for it and keep the first status.
