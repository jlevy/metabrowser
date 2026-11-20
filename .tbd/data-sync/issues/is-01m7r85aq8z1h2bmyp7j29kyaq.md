---
type: is
id: is-01m7r85aq8z1h2bmyp7j29kyaq
title: "Flake: wall-clock limits in HealthCheckTests and RepositoryStartupTests under load"
kind: bug
status: open
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-18T21:14:17.695Z
updated_at: 2026-11-20T17:20:12.145Z
---
Failed once in a full 'swift test' run (602 tests) on 2026-11-18 while the machine was loaded (suite took 11.4 s); passed 3 of 3 in isolation (0.24 s). Seen on the folder-switching stack (mb-32yq), which does not touch supervision. Likely a timing assumption in the test's hung-server deadline; reproduce under CPU load before fixing.

2026-11-18, second run (610 tests, layer 3 of the stack): HealthCheckTests.aServerThatStopsAnsweringIsStoppedAndFailsWithTheReason measured 2.007 s against a 2 s bound (HealthCheckTests.swift:76), and StartupDeadlineTests.swift:160 (RepositoryStartupTests.aStartThatGoesQuietIsGivenUpOnLongBeforeItsLimit) measured 13.7 s against 10 s. Both suites passed together in isolation (2.5 s). Both assert wall-clock durations on ContinuousClock in a parallel run.
