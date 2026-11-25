---
type: is
id: is-01m84s4gv2cynykbv302f8ykn4
title: Startup scripts sit 2 bytes under their 220 KB budget
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
created_at: 2026-11-23T18:01:50.177Z
updated_at: 2026-11-25T02:16:20.156Z
---
After rebasing the treemap stack (stack #725) on main 55e8365, devtools/check_startup_scripts.py reports 225,789 bytes transferred, 2 bytes under the 220 KB budget in explorations/performance-loop/performance-budgets.toml. Layer 5 (#754) shrank fetchRollup's query-key list in plugin-sdk.js to get under; the next growth of an eager script will fail lint-check. Decide: move code the first tree does not need out of the eager tier (arch-browser-shell.md, Asset Loading Tiers), or remeasure the budget.
