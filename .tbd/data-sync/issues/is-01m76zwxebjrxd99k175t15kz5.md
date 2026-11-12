---
type: is
id: is-01m76zwxebjrxd99k175t15kz5
title: Supervisor deadlines measured against main-actor stalls
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T04:22:48.010Z
updated_at: 2026-11-12T04:22:48.010Z
---
From the #341 CI investigation: the readiness loop checks its deadline before the first probe, and abandon decides 'timed out' from a clock read taken after resuming. A main-actor stall longer than the startup timeout (60 s in production) could report a server that would answer as timed out. Probe once before judging the deadline, and base timeouts on monotonic time spent waiting rather than on resume time.
