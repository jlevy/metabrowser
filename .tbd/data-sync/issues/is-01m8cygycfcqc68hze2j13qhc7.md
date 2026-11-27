---
type: is
id: is-01m8cygycfcqc68hze2j13qhc7
title: Prepare the initial Commits history page during server startup
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/898
    at: 2026-11-26T22:21:53.492Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
child_order_hints:
  - is-01m8cz8j6sf5x8vy24fnpwv75b
hold: null
hold_until: null
created_at: 2026-11-26T22:09:55.591Z
updated_at: 2026-11-27T11:22:32.719Z
started_at: 2026-11-26T22:11:15.310Z
closed_at: 2026-11-27T11:22:32.718Z
close_reason: "Merged in the exact reviewed performance stack #899 at main 4313286. Each owning layer passed its hosted workflow."
resolution: null
duplicate_of: null
---
H125. Prepare the normal first history page once through the existing reader on a fresh server. Compare startup and first history through real HTTP with equal contents, and verify that a concurrent click shares the producer. Branch codex/prefetch-commit-history.
