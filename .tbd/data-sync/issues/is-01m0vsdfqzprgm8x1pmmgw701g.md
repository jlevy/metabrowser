---
type: is
id: is-01m0vsdfqzprgm8x1pmmgw701g
title: Validate unbounded Git history for the v0.9.0 release
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
delegate: codex@spud10.local
labels:
  - release:v0.9.0
dependencies: []
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
hold: null
hold_until: null
created_at: 2026-08-25T06:23:41.310Z
updated_at: 2026-08-27T07:24:36.150Z
started_at: 2026-08-27T06:54:32.466Z
closed_at: 2026-08-27T07:24:36.137Z
close_reason: Completed the nine-corpus backend and headed browser matrices, forced 1.45-million-row segment rebasing, fixed the cached stylesheet settlement defect, passed exact installed-wheel v0.8.0 comparison, make verify, pre-push, and all five GitHub checks, and committed durable evidence in exp-020 and the completed spec.
resolution: null
duplicate_of: null
---
Add behavior tests for paging, virtualization, keyboard and pointer selection, direct commit routes, failures, retries, ref changes, and end of history. Run real-browser measurements across the planned corpora, verify mounted resources remain within the recorded budgets while logical history grows, update architecture and large-content guidance, run make verify, and complete release-candidate comparison.

## Notes

Phase 5 complete at exact code head 1c7bdf8. Backend matrix passed all nine frozen linear, branch-heavy, and merge-heavy corpora at 250, 1,000, and 10,000 commits: exact ordering, 40 pages at each deepest case, 114,071-byte maximum parser buffer under 128 KiB, 194.417 maximum spool bytes per commit, 16.969 MiB maximum Git RSS, and exact first/middle/final replay. Nine headed profiles reached exact end with bounded rows and heap, complete sampled replay, exact deepest selection/direct route, one comparison, and zero blank frames, divergence, exceptions, or Long Tasks. The matrix found a cached stylesheet load-event stall; the generic loader now detects link.sheet, settles idempotently, and has a 10-second fallback, with browser-shim coverage and three repeated passing merge-heavy 1,000 and 10,000 runs. The 1,454,667-row synthetic gate forced both rebase directions, preserved anchors, measured 7,999,992 px under budget, restored the near-end target, mounted at most 170 rows, and raised no exception. Exact installed 1c7bdf8 passed make verify (1,596 tests, 48 golden scenarios) and exact headed 10,000-row merge-heavy plus segment-rebase reruns. Five backend pairs and six interleaved headed profiles against installed v0.8.0 preserve rows/tallies and pass every hard gate. Durable evidence is in the Git-history README and exp-020. Pending only the evidence commit/push, final CI, bead closure, and PR readiness.
