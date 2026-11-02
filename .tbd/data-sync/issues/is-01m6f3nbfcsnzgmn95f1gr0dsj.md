---
type: is
id: is-01m6f3nbfcsnzgmn95f1gr0dsj
title: Independent review of the mirror and checkout design
kind: task
status: closed
priority: 1
version: 4
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6f3nbz5f5rbwbjcs64vj4g2
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:48.171Z
updated_at: 2026-11-02T21:49:59.647Z
started_at: 2026-11-02T21:47:05.769Z
closed_at: 2026-11-02T21:49:59.646Z
close_reason: "Independent review done 2026-11-02: sound with changes. Two blockers proven on replicas: a copied shallow boundary makes merge-base silently wrong rather than empty, and seeded refs get published as the origin's, including from a hostile working directory. Two high findings: a dangling non-PR ref wedges every fetch, and healing after a force-push cannot restore the shown commit. Four medium and five low. Reproduced 3.9 s acquisition and a byte-identical comparison. Applied under mb-shwd."
resolution: null
duplicate_of: null
---
Running. Attacks silent wrongness (shallow boundary and wrong merge base), security including a hostile working directory, worktree layouts, the no-loss relaxation, and whether the design is simpler than it looks. Reproduces the headline numbers.
