---
type: is
id: is-01m0g3jsy9kprhy5a6k6x514b5
title: "Route the shell's remaining selections: /compare and panel state"
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-20T17:30:28.168Z
updated_at: 2026-08-20T17:30:28.168Z
---
The Browser URL Grammar now defines one route per address space and /commit/<rev>[/<file>] is implemented. Remaining: /compare/<base>..<head>[/<file>] for explicit comparisons (the grammar is specified, the git source already resolves both two-dot and three-dot), selecting an inner file from a /commit/ route on load (currently the route restores the commit, not the file), and an audit that every panel that changes the main pane changes the URL.
