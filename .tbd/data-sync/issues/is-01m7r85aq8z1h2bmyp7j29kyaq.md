---
type: is
id: is-01m7r85aq8z1h2bmyp7j29kyaq
title: "Flake: HealthCheckTests.aServerThatStopsAnsweringIsStoppedAndFailsWithTheReason under load"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T21:14:17.695Z
updated_at: 2026-11-18T21:14:17.695Z
---
Failed once in a full 'swift test' run (602 tests) on 2026-11-18 while the machine was loaded (suite took 11.4 s); passed 3 of 3 in isolation (0.24 s). Seen on the folder-switching stack (mb-32yq), which does not touch supervision. Likely a timing assumption in the test's hung-server deadline; reproduce under CPU load before fixing.
