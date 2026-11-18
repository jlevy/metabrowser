---
type: is
id: is-01m7pkgzth175ysqyfpp41brk9
title: "Startup-script budget: re-derive the ceiling or free bytes structurally before the view header's next step"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7pab7r3k7xe521vyg5xmrgb
created_at: 2026-11-18T05:54:25.232Z
updated_at: 2026-11-18T05:54:25.232Z
---
Review A on #552, A3 step 3 (the coordinator takes it to the owner). The startup-script budget (explorations/performance-loop/performance-budgets.toml, startup_script_transfer_kb, 220 KB as the remote path sends it) has about 25 bytes left after #550 and #552; #550 spent a net ~563 of the ~600 bytes main had, by cutting its own comments, and the coordinator has ruled out paying further with comments and types. devtools/check_startup_scripts.py now also reports, ungated, a github.com checkout's inline bytes (its repository context and github-page.js), which the gate's count of requested scripts never sees. Decide before mb-7t5s adds header code: re-derive the ceiling as the budget file prescribes, or free bytes structurally, for example stripping comments at delivery (the budget file says comments are 41% of the bytes), or moving first-paint builders behind a tier.
