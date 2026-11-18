---
type: is
id: is-01m7pkgzth175ysqyfpp41brk9
title: "Startup-script budget: re-derive the ceiling or free bytes structurally before the view header's next step"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7pab7r3k7xe521vyg5xmrgb
created_at: 2026-11-18T05:54:25.232Z
updated_at: 2026-11-18T07:00:32.233Z
---
Review A on #552, A3 step 3 (the coordinator takes it to the owner). The startup-script budget (explorations/performance-loop/performance-budgets.toml, startup_script_transfer_kb, 220 KB as the remote path sends it) has about 25 bytes left after #550 and #552; #550 spent a net ~563 of the ~600 bytes main had, by cutting its own comments, and the coordinator has ruled out paying further with comments and types. devtools/check_startup_scripts.py now also reports, ungated, a github.com checkout's inline bytes (its repository context and github-page.js), which the gate's count of requested scripts never sees. Decide before mb-7t5s adds header code: re-derive the ceiling as the budget file prescribes, or free bytes structurally, for example stripping comments at delivery (the budget file says comments are 41% of the bytes), or moving first-paint builders behind a tier.

## Notes

2026-11-18 review B on #552 (B8, a suggestion folded here): static/github-page.js reads branch_on_origin from the raw window.METABROWSER_REPOSITORY_CONTEXT beside the SDK's validated metabrowser.repository, and types.d.ts marks the field optional on the SDK's type to allow it: one context split into two sources to save startup-script bytes. Once bytes are free, the SDK's copy (plugin-sdk.js normalizeRepositoryContext) should carry branch_on_origin and github-page.js read only it.
2026-11-18 review B on #552 (B2), fixed at 027599fd4: devtools/check_startup_scripts.py's checkout line no longer reports "inline script (its repository context and github-page.js)", which counted the whole bundle manifest too; it reports how much more the application sends for a github.com checkout's shell than for a plain folder's (3,134 bytes, +/- 2 between runs, at that head). The folder shell's gated margin is 25 bytes at #552 and 38 at #550 (8b553a06d); #550's B1 fix was made in CSS because the JS form in tipAnchorIsCut cost 31 to 102 bytes.
