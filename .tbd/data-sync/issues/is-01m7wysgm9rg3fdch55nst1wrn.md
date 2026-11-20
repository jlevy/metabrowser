---
type: is
id: is-01m7wysgm9rg3fdch55nst1wrn
title: "CI speed: finish the Fast CI plan and verify its phases"
kind: epic
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
child_order_hints:
  - is-01m7m3rn4x4ttt604xrtj32vff
  - is-01m7m5vfv9h31f3b6hha08r57z
  - is-01m7ks85cztbqgy4bw9ntv7c7s
  - is-01m7kpnfbtzejh3redbeppejmp
  - is-01m7kpnew2rrszv4ekchm6c75z
  - is-01m7pj8gve71bkvxyw96nqa4yn
  - is-01m7pjrkn0aprh3pz0m4ba5ff6
created_at: 2026-11-20T17:06:45.512Z
updated_at: 2026-11-20T17:19:01.064Z
---
The owner asked on 2026-11-16 for a pull request's gate in 3 to 5 minutes at the same coverage. The assessment and plan merged in #496 (docs/project/specs/active/plan-2026-11-16-fast-ci.md); Phase 1 (#499, four processors) and Phase 2 (#504, parallel jobs with one ci-ok verdict) are merged, and the first measured pull requests took 4.7 to 5.5 minutes.

What remains: finish Phase 1's 10-run acceptance (mb-g0xx), verify Phase 2 after the merge (mb-ohsk), the owner's branch ruleset requiring ci-ok (mb-m4ct), and Phase 3 (path classes mb-pvyg, the serial tier's fixed waits mb-37dw, the Chrome start retry and per-test allowances mb-sicb and mb-bl54). Flaky tests are tracked under mb-1qsn.
