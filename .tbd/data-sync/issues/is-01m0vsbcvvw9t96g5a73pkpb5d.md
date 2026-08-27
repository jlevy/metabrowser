---
type: is
id: is-01m0vsbcvvw9t96g5a73pkpb5d
title: Measure Git history cost and define structural budgets
kind: task
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies:
  - type: blocks
    target: is-01m0vscnvzcjatq9nd43zvqnwa
  - type: blocks
    target: is-01m0vscy963c6aphv6ga8wmxww
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:22:32.826Z
updated_at: 2026-08-27T03:54:29.693Z
closed_at: 2026-08-27T03:54:29.692Z
close_reason: Completed the deterministic 250/1,000/10,000-commit linear, branch-heavy, and merge-heavy backend and headed-browser matrix. Exact date-order/replay checks passed; measured evidence and the accepted one-walk spool design are recorded in explorations/git-history/README.md. Frozen bounded session, parser, storage, page-cache, DOM-window, overscan, and segment-rebase budgets are enforced structurally. Full make verify passed with 1,572 tests and 48 golden scenarios.
resolution: null
duplicate_of: null
---
Build deterministic Git-history corpora at multiple depths and branch shapes; measure API latency, skip-depth growth, payload bytes, retained client data, DOM nodes, renderer memory, append/layout cost, scrolling, selection, and deep-route restoration in a real browser. Establish the cost shape and record measurements beside every resulting budget. Add stable contract assertions for structural bounds rather than wall-clock CI tests.

## Notes

Started from public v0.8.0 at exact commit 552f0843318655eb9090aaeaff00a679665d56f2 on codex/unbounded-git-history. Phase 1 only: build deterministic history corpora, measure server/browser/continuation cost shapes, prototype page replay, and freeze structural budgets before mb-abu2 or mb-ghju begins. No implementation budget is accepted without recorded evidence beside its constant.
