---
type: is
id: is-01m0vhn0d852431fzr1tbcth4h
title: "H63: Reject rendered browser failures and isolate release adapters"
kind: bug
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0vdm7d6j696m0acyqxsq215
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
hold: null
hold_until: null
created_at: 2026-08-25T04:07:59.136Z
updated_at: 2026-08-25T04:43:59.964Z
started_at: 2026-08-25T04:09:27.749Z
closed_at: 2026-08-25T04:43:59.963Z
close_reason: Corrected the v0.6.0 measurement adapter, added hard rendered-error and page-exception gates, isolated harness processes and provenance, and completed four clean release-versus-candidate browser pairs.
resolution: null
duplicate_of: null
---
The release comparison harness certified v0.6 browser profiles whose largest-contentful element was a rendered preview-error panel and whose page emitted SDK exceptions. Add hard gates for rendered preview errors and uncaught page exceptions, prove the former profiles fail, and rebuild the immutable v0.6 measurement adapter from the exact tag without checkout contamination before rerunning release-versus-candidate captures. This is measurement infrastructure, not a production compatibility layer.

## Notes

Harness 15 now counts #preview-pane .preview-error states and CDP Runtime.exceptionThrown events, requires both to be zero, isolates external builds from the checkout, records real-tree file counts from walk_files, and stops only its recorded server PID after command verification. The broken adapter deterministically records one rendered error and eight exceptions; the rebuilt exact-tag adapter and candidate each record zero across four admissible headed profiles. make verify passes with 1,523 tests and 48 goldens.
