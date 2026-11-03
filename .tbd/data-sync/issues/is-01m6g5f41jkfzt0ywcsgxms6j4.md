---
type: is
id: is-01m6g5f41jkfzt0ywcsgxms6j4
title: Repair overlay merge-base certainty and lender sweep edge cases
kind: bug
status: in_progress
priority: 1
version: 3
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T07:37:35.538Z
updated_at: 2026-11-03T07:50:37.693Z
started_at: 2026-11-03T07:38:10.112Z
---
Audit PR #283 at 483e3a83 and checkout draft #288. Preserve valid criss-cross merge bases on Git 2.43; reproduce timeout persistence and missing pack index sweep before focused fixes.

## Notes

Focused fixes committed a51cc866: pre-2.45/unknown Git verifies complete visible history, modern Git keeps short walk; criss-cross accepted; timeout/output bound preserve record as comparison_timeout/comparison_too_large; missing pack index and missing store record cannot authorize blind fetch/sweep; changed FIFO boundary refused; failed boundary replace cleans temporary symlink; exit1 verification rereads boundary after walk. Reproductions failed before fixes. 120 overlay tests passed plus new boundary race test; Ruff and BasedPyright passed. Synthetic 200000 commits: modern median 0.0213s, simulated old-Git safety path 0.9098s across 5 runs. Real Git2.43 confirmation and full make verify/CI remain coordinator gates. Self-review only for authored fixes; root independent review pending.
