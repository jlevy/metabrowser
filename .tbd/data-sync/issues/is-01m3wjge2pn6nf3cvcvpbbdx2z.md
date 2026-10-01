---
type: is
id: is-01m3wjge2pn6nf3cvcvpbbdx2z
title: "Release rehearsal for v0.12 before landing: the standard release checklist's stability steps against v0.11.0"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T20:29:17.780Z
updated_at: 2026-10-01T20:29:25.531Z
started_at: 2026-10-01T20:29:25.524Z
---
The user, 2026-10-01: 'We have a standard release process to check for stability and no regressions on features or performance. Let's go ahead and run that early before we land this entire stack. Since there are so many changes, there's quite a bit of risk.' Run docs/publishing.md's Release Checklist steps 1-5 as a rehearsal on the stack's candidate, without tagging, releasing or merging: (2) the complete 'make verify'; (3) the previous-release performance loop (explorations/performance-loop/README.md, 'Comparing a candidate with the previous release') against v0.11.0, recorded as a committed experiment with the performance report regenerated; every candidate run must pass the hard responsiveness and correctness gates, and a repeatable wrong-way metric blocks until fixed or explicitly accepted by the user; read the backend comparison's equivalence (differing rows is a regression until shown otherwise; differing tallies must be confined to what the changelog describes); (4) CI green on the exact candidate commit; (5) review the changes since v0.11.0 and propose the version. Steps 6-10 (tag, publish, post-release checks) are not run. Re-run on the final tip before the landing decision. Related gates: mb-2g6f (regular-folder differentials), mb-67s1 (wall-clock pairs on a quiet machine).
