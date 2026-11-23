---
type: is
id: is-01m82ws2a43qqsts4htzqjepwz
title: "macOS app: a folder's log lock outlived its lease's release in LogLeaseTests on CI"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T00:27:00.276Z
updated_at: 2026-11-23T06:36:15.681Z
started_at: 2026-11-23T06:36:15.661Z
---
CI run 45087245135 (macOS 26, Xcode 26.6), PR #709 head 035c7f79b, which changes no Swift: LogLeaseTests.theFirstClaimGetsTheFoldersLogAndASecondGetsItsOwn failed at LogLeaseTests.swift:27 — after `first = nil`, the third claim found the shared log's flock still held and took notes-<hash>.app-300.log. Only this test opens that lock file (a per-test temporary folder), so the held lock is the first lease's own open file description: either the lease was not deinitialized at `first = nil`, or another descriptor referenced that description. Ruled out: inheritance by spawned children (every posix_spawn sets POSIX_SPAWN_CLOEXEC_DEFAULT and the lock is O_CLOEXEC); a stray double close elsewhere (it would release the lock early and fail line 22, not 27); exit tests (none). Not reproduced in six local runs of the ShellCore suite (Swift 6.3.3, load average ~400). Not seen in the 40 macOS runs before it. Candidates to check: whether Swift Testing's #expect capture of `first?.url` retains the lease; a posix_spawn file action dup2 of a stale fd number (ServerProcess passes log?.handle.fileDescriptor). Done: the mechanism named, and a fix or a test that cannot depend on it.
