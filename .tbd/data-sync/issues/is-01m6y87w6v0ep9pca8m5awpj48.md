---
type: is
id: is-01m6y87w6v0ep9pca8m5awpj48
title: Retry failed expanded folders when the server reconnects
kind: bug
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex/quiet_release_comparison
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
created_at: 2026-11-08T18:55:25.914Z
updated_at: 2026-11-08T19:32:33.695Z
---
Fresh exact426 browser comparison reproduces a persistent Files-tree recovery regression in 7.errors-server-restart, both wide/narrow light. Expanded docs remains tree-lazy-error after server restart through steps05–08, an8-second wait, selecting README, opening data and discovery of after-restart.txt; docs/guide.md remains absent. Control0.11 recovers docs children at05. Current onopen retries preview/catalog but not failed expanded subtrees, whose error asks for manual collapse/reopen. Preserve raw captures/source proof and add a focused production-session regression. On real connection restoration, retry only failed expanded subtree loads, retaining existing successful content, collapsed-node behavior, in-flight deduplication and source/disposal boundaries. Use the existing connection/file-watch mechanisms; no generic retry loops, redundant status lines or compatibility branch. Root owns implementation after frozen input integrity checks; reviewed final build/full gate/CI/manual recovery required. Evidence: full396-restoration-proposal-20261108T175109Z.

## Notes

November 8: corrected recovery is committed locally at c83c3178e4ec495d0cfa3472a36d95702b096737. Independent frontend review caught and resolved the identical-snapshot bypass; actual EventSource listener tests now cover unchanged sentinels, failed-path-only cache/request invalidation, one filtered root recovery, stale-answer rejection and retained logical disclosure under a collapsed ancestor. Two real red cases are preserved; 25 focused tests, two golden commands, both browser type projects and parity97 pass. The first normal pre-push full make verify attempt stops before pytest: startup-script transfer is180160 bytes,449 over the existing175KB gate. Full lint, Python typing (zero errors/warnings), hygiene and parity checks passed before that failure. Branch is not yet pushed or installed. Implementer is measuring a minimal maintainable size correction; budget remains unchanged. All original evidence remains separate. Full gate, CI, final artifact/manual qualification and merge remain pending.
