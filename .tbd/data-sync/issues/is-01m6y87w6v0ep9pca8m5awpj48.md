---
type: is
id: is-01m6y87w6v0ep9pca8m5awpj48
title: Retry failed expanded folders when the server reconnects
kind: bug
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex/quiet_release_comparison
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
created_at: 2026-11-08T18:55:25.914Z
updated_at: 2026-11-08T23:44:46.787Z
closed_at: 2026-11-08T23:44:46.787Z
close_reason: "Delivered in PR #337 with scoped installed validation, merged-main CI and proof in the delivery notes."
resolution: null
duplicate_of: null
---
Fresh exact426 browser comparison reproduces a persistent Files-tree recovery regression in 7.errors-server-restart, both wide/narrow light. Expanded docs remains tree-lazy-error after server restart through steps05–08, an8-second wait, selecting README, opening data and discovery of after-restart.txt; docs/guide.md remains absent. Control0.11 recovers docs children at05. Current onopen retries preview/catalog but not failed expanded subtrees, whose error asks for manual collapse/reopen. Preserve raw captures/source proof and add a focused production-session regression. On real connection restoration, retry only failed expanded subtree loads, retaining existing successful content, collapsed-node behavior, in-flight deduplication and source/disposal boundaries. Use the existing connection/file-watch mechanisms; no generic retry loops, redundant status lines or compatibility branch. Root owns implementation after frozen input integrity checks; reviewed final build/full gate/CI/manual recovery required. Evidence: full396-restoration-proposal-20261108T175109Z.

## Notes

November 8: corrected recovery is committed locally at c83c3178e4ec495d0cfa3472a36d95702b096737. Independent frontend review caught and resolved the identical-snapshot bypass; actual EventSource listener tests now cover unchanged sentinels, failed-path-only cache/request invalidation, one filtered root recovery, stale-answer rejection and retained logical disclosure under a collapsed ancestor. Two real red cases are preserved; 25 focused tests, two golden commands, both browser type projects and parity97 pass. The first normal pre-push full make verify attempt stops before pytest: startup-script transfer is180160 bytes,449 over the existing175KB gate. Full lint, Python typing (zero errors/warnings), hygiene and parity checks passed before that failure. Branch is not yet pushed or installed. Implementer is measuring a minimal maintainable size correction; budget remains unchanged. All original evidence remains separate. Full gate, CI, final artifact/manual qualification and merge remain pending.

November 8, final c3 delivery (merge pending): PR #337 at c3d093d2d222ddce74568e7c74111e2cc0c57d3f passed normal-hook full make verify in 1438.51 seconds: 4929 Python passes, nine expected skips and 388 goldens, with lint/types, both audits, distribution and installed-wheel smoke checks; filesystem observer zero bytes. All nine PR CI jobs passed in workflow 42518226853. Exact wheel 0.11.1.dev1290+c3d093d2d is installed for both aliases and all three retained previews, with eleven healthy plugins, 45 unchanged pins and 45 served-asset comparisons. Independent reviews A/B/C cover the fixes and D covers the comment-only startup correction; the 175 KB budget remains unchanged. Original failed gate and 426 comparison evidence remain preserved. No merge, quiet performance or owner release acceptance is claimed. Keep this bead open until root reconciles the actual merge. Public references: https://github.com/jlevy/metabrowser/pull/337 and https://github.com/jlevy/metabrowser/actions/runs/42518226853.

Installed built-in-browser recovery passes after an actual expanded docs folder error while the owned server is offline. The same page automatically restores children and clears the error when the server returns, without Reload, collapse/reopen or intervening navigation. An early locator deadline and the expected offline Failed to fetch warning remain preserved; no elapsed-time claim. Automated actual-listener sessions separately prove identical-sentinel recovery, healthy-cache retention and stale-answer rejection.

November 8 actual delivery. Native stack #339 atomically merged PRs #337, #336, #340 and #342 into main a2677882a2281a1e5b622acf4788ded9e5516331 from 23:27:15 to 23:27:18 UTC. Its tree 8d69ce06a4054c4a394248c36ba05e12ddd38fcc matches qualified installed b2fb exactly. All four PRs and merged main passed nine CI contexts. https://github.com/jlevy/metabrowser/actions/runs/42535251691

The reviewed reconnect fix landed in #337. Exact installed c3 automatically recovered a genuinely failed expanded docs folder after the owned server restarted, without Reload or collapse/reopen. The identical-sentinel regression and original exact 426 failure remain separately documented.
