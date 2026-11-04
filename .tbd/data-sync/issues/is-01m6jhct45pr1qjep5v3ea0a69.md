---
type: is
id: is-01m6jhct45pr1qjep5v3ea0a69
title: Run integrated code and end-to-end review on landed main
kind: task
status: in_progress
priority: 1
version: 5
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
updated_at: 2026-11-04T14:58:13.126Z
started_at: 2026-11-04T13:48:45.620Z
---
Reviewcompleteintegratedmain bybackend acquisition/cache/account/shallow/worktree safety, frontend/rendering/performance/design/Markdown/assets, dependencies/CLI/stackmetadata. Runfocusedautomated+manualsessions for bothmanagedrepo andexisting/linkedcheckouts; cold/warm/restart/incremental/5000catalog/largefile flows; consistentmeasurementprovenance. Fullnormalgate/exactartifactacceptance. Fixrealfindings inreviewedforwardPRs, no blanketno-errors/speedclaims.

## Notes

2026-11-04: The postlanding review found and reproduced the account-switch prefix-publication regression on feature main da87bb13. Its forward fix is now merged as PR #297 at afaf38b85a83443e25002765203c216bd11f8dfa. Exact whole-tree equality preserves candidate verification provenance; tests are not relabeled as runs at the merge SHA. Independent current-main reconciliation and current-main CI are pending. This review phase remains in progress.
