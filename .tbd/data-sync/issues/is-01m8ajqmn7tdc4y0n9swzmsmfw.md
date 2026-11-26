---
type: is
id: is-01m8ajqmn7tdc4y0n9swzmsmfw
title: Open the PR, watch CI to green
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/860
    at: 2026-11-26T00:53:38.436Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8ahev7t0174z3a2vhhnpw81
hold: null
hold_until: null
created_at: 2026-11-26T00:05:23.238Z
updated_at: 2026-11-26T00:53:38.436Z
started_at: 2026-11-26T00:20:04.132Z
---
make verify (environment-only failures compared against origin/main), PR via create-or-update-pr-simple, record it on the epic, watch CI.
