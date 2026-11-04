---
type: is
id: is-01m6jhct45pr1qjep5v3ea0a69
title: Run integrated code and end-to-end review on landed main
kind: task
status: closed
priority: 1
version: 8
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6jhctf78vq1v7ndv43jzssy
parent_id: is-01m6jhcsrvevhaa1kg3fh6g8zg
child_order_hints:
  - is-01m6kc1q2z4b9wrmt6qb90t0vj
hold: null
hold_until: null
created_at: 2026-11-04T05:44:31.620Z
updated_at: 2026-11-04T17:21:04.003Z
started_at: 2026-11-04T13:48:45.620Z
closed_at: 2026-11-04T17:21:04.002Z
close_reason: Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate.
resolution: null
duplicate_of: null
---
Reviewcompleteintegratedmain bybackend acquisition/cache/account/shallow/worktree safety, frontend/rendering/performance/design/Markdown/assets, dependencies/CLI/stackmetadata. Runfocusedautomated+manualsessions for bothmanagedrepo andexisting/linkedcheckouts; cold/warm/restart/incremental/5000catalog/largefile flows; consistentmeasurementprovenance. Fullnormalgate/exactartifactacceptance. Fixrealfindings inreviewedforwardPRs, no blanketno-errors/speedclaims.

## Notes

2026-11-04: The postlanding review found and reproduced the account-switch prefix-publication regression on feature main da87bb13. Its forward fix is now merged as PR #297 at afaf38b85a83443e25002765203c216bd11f8dfa. Exact whole-tree equality preserves candidate verification provenance; tests are not relabeled as runs at the merge SHA. Independent current-main reconciliation and current-main CI are pending. This review phase remains in progress.

2026-11-04: Actual account-fix main afaf38b85a83443e25002765203c216bd11f8dfa now passes all nine current-main CI jobs and the clean independent integrated reconciliation, published at https://github.com/jlevy/metabrowser/pull/297#pullrequestreview-5770654024 . Bead mb-dvhc is closed after actual merge/review/CI verification. Prior source/full-gate/noneditable tests retain their executed cc93 pin and are inherited by exact tree equality. This broader integrated code/E2E phase remains in progress for final documentation-main reconciliation and actual final installed-build/manual acceptance.

2026-11-04 completion: all 21 feature PRs and follow-ups #297/#298 are merged at https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Final integration review https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263 is clean; all nine actual-main CI jobs passed at https://github.com/jlevy/metabrowser/actions/runs/41868009781. Full make verify and normal push each passed 4,786 Python tests, nine expected skips and 378 golden commands at tree-identical commit 3f5bd2d3. Fresh final wheel passed eight public live tests, six installed regressions and 21 UI checks; root seven-image visual and actual installed-server manual checks passed. Both global aliases and previews use verified 0.11.1.dev1154+db52ec09, all 341 package bytes match, old servers are stopped, portable/host skill is current, and production cache admission passed after volume permissions were restored. Maintained documentation, all 37 plans, 124 mapped pointers, six historical pointer retirements and 25 current-status notes are reconciled. 107 scoped delivered tasks are closed. Genuine partial/future, quiet-performance and release work stays open; draft #247, both WIPs, issue relationships and protected config are preserved. No release tag or publication is implied.
