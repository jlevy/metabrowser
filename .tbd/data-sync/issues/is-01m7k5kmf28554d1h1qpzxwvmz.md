---
type: is
id: is-01m7k5kmf28554d1h1qpzxwvmz
title: "PR #485 A19: Run syspolicy_check notary-submission before each submission"
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
created_at: 2026-11-16T21:53:28.545Z
updated_at: 2026-11-16T22:10:04.401Z
started_at: 2026-11-16T21:53:43.052Z
closed_at: 2026-11-16T22:10:04.400Z
close_reason: "Fixed in 83ef69fc3: mb-tfap runs syspolicy_check notary-submission before each submission."
resolution: null
duplicate_of: null
---
Suggestion. It runs the notary service's checks locally, so a rejection is caught before a round trip that counts against the daily limit. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
