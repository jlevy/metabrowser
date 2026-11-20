---
type: is
id: is-01m7pkgzth175ysqyfpp41brk9
title: "Startup-script budget: re-derive the ceiling or free bytes structurally before the view header's next step"
kind: task
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: null
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
hold: null
hold_until: null
created_at: 2026-11-18T05:54:25.232Z
updated_at: 2026-11-20T17:24:34.616Z
started_at: 2026-11-18T21:06:43.653Z
---
Review A on #552, A3 step 3 (the coordinator takes it to the owner). The startup-script budget (explorations/performance-loop/performance-budgets.toml, startup_script_transfer_kb, 220 KB as the remote path sends it) has about 25 bytes left after #550 and #552; #550 spent a net ~563 of the ~600 bytes main had, by cutting its own comments, and the coordinator has ruled out paying further with comments and types. devtools/check_startup_scripts.py now also reports, ungated, a github.com checkout's inline bytes (its repository context and github-page.js), which the gate's count of requested scripts never sees. Decide before mb-7t5s adds header code: re-derive the ceiling as the budget file prescribes, or free bytes structurally, for example stripping comments at delivery (the budget file says comments are 41% of the bytes), or moving first-paint builders behind a tier.

## Notes

2026-11-18 review B on #552 (B8, a suggestion folded here): static/github-page.js reads branch_on_origin from the raw window.METABROWSER_REPOSITORY_CONTEXT beside the SDK's validated metabrowser.repository, and types.d.ts marks the field optional on the SDK's type to allow it: one context split into two sources to save startup-script bytes. Once bytes are free, the SDK's copy (plugin-sdk.js normalizeRepositoryContext) should carry branch_on_origin and github-page.js read only it.
2026-11-18 review B on #552 (B2), fixed at 027599fd4: devtools/check_startup_scripts.py's checkout line no longer reports "inline script (its repository context and github-page.js)", which counted the whole bundle manifest too; it reports how much more the application sends for a github.com checkout's shell than for a plain folder's (3,134 bytes, +/- 2 between runs, at that head). The folder shell's gated margin is 25 bytes at #552 and 38 at #550 (8b553a06d); #550's B1 fix was made in CSS because the JS form in tipAnchorIsCut cost 31 to 102 bytes.
2026-11-18 the budget question, resolved structurally at #550 ae6ad263b and #552 8ddcb4b1c, with the ceiling unchanged and no comment or type cut: the view header's builders moved from app.js to static/view-header.js, an on-demand `view-header` bundle that loadViewComposition fetches in parallel with the compositor and the SDK's view helpers. renderFile draws a header only after that, so they were never first-paint code. devtools/check_startup_scripts.py: #550 went from 226,291 bytes (500 over, after merging main a1100bca6) to 222,991 (2,800 under); #552 from 225,966 (175 over, at 3a075232e) to 222,991 (2,800 under), its data-path now in view-header.js, and its ungated github.com checkout's shell from 229,099 (3,308 over) to 226,285 (494 over). Chrome, 36 cold loads of a folder and of a file a side in alternating back-to-back pairs at load averages of 24 to 33 on 10 cores: the header's median time after DOMContentLoaded went from 40 to 41 ms on a folder and stayed at 58 ms on a file; recorded beside the bundle in server.py and in the budget's note. mb-7t5s's header code now lands in view-header.js, off the eager tier. Left open only for B8 above, which spends eager bytes in plugin-sdk.js and now has room.
