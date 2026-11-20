---
type: is
id: is-01m7rhv61js9th33xvb82q4ahh
title: "Flaky macOS test: LogLeaseTests.overlappingClaimsOfOneCopyEachGetALogOfTheirOwn"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-19T00:03:30.989Z
updated_at: 2026-11-20T17:20:22.368Z
---
Failed once in CI on jlevy/metabrowser#587 (run 44423821362, job 135223365570), a change that touches no Swift outside AppDelegate.openFolder: after claims[1] = nil, the next claim got <stem>.app-100-3.log, not <stem>.app-100.log, so the released lease's name was still held. LogLeaseTests.swift:50. Passes locally. Suspect the lease's release depends on when the dropped ServerLogLease is deinitialized (or a lock released asynchronously); make the test release explicitly, or make the claim's release deterministic.
