---
type: is
id: is-01m7k5kf0rmrxa29s51s9csa42
title: "PR #485 A9: The never-on-a-command-line goal does not hold for the keychain recipe the plan adopts"
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
created_at: 2026-11-16T21:53:22.967Z
updated_at: 2026-11-16T22:09:58.410Z
started_at: 2026-11-16T21:53:39.178Z
closed_at: 2026-11-16T22:09:58.409Z
close_reason: "Fixed in 83ef69fc3: Goals restated: never in the repository or a log; typed at prompts on the owner's Mac; on the ephemeral runner as arguments with tracing off (mb-3ey5)."
resolution: null
duplicate_of: null
---
Low. PLAN:56, :331-333, :474-478. security import -P and the keychain commands take passwords as arguments. Fix: restate the goal (never in the repository or a log; on the ephemeral runner they reach security only as arguments, tracing off), or name a mechanism that keeps them off argv. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
