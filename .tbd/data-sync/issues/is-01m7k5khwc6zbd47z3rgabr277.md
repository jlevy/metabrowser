---
type: is
id: is-01m7k5khwc6zbd47z3rgabr277
title: "PR #485 A14: The quarantine simulation and decoding depend on the attribute's unsupported format"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:25.899Z
updated_at: 2026-11-16T22:10:02.242Z
started_at: 2026-11-16T21:53:41.089Z
closed_at: 2026-11-16T22:10:02.239Z
close_reason: "Fixed in 83ef69fc3: the simulated quarantine goes through URLResourceKey.quarantinePropertiesKey with a small Swift helper, recorded in mb-xd4o's scope; mb-4hwg prints decoded fields as information only."
resolution: null
duplicate_of: null
---
Low. PLAN:443-444, :454-455, :531-532. Fix: apply the simulated quarantine through URLResourceKey.quarantinePropertiesKey with a small Swift helper (mb-xd4o's scope), and print decoded fields as information only. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
