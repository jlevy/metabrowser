---
type: is
id: is-01m0y74n2yd54hyz6kqn93xsw4
title: Large folded diffs materialize hidden rows and block the main thread
kind: bug
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
  - type: blocks
    target: is-01m0y5hw7w8fdw9herhmph9qqs
parent_id: is-01kxse0wddy6je24t1dm5caber
created_at: 2026-08-26T05:02:00.786Z
updated_at: 2026-08-26T06:23:10.908Z
closed_at: 2026-08-26T06:23:10.907Z
close_reason: Large folded comparisons now have bounded initial DOM and cooperative cancellable expansion, with automated gates and exact-build browser validation complete.
resolution: null
duplicate_of: null
---
Reproduced on exact globally installed c76d9ab against trading commit 4cad9590bb1f2c82ec9ff1487d89d880cd2153dc. The 1,260,594-byte comparison has 19,654 diff lines, including changed runs of 18,211 and 1,130 lines. Initial mount constructs every folded row and produced a 1,475 ms main-thread block; a deferred setTimeout diff enhancement produced a second 900 ms long animation frame. Implement measured lazy folded-row materialization and bounded/cooperative enrichment so collapsed content does not exist in the initial DOM, expansion preserves exact text/layout/fold state, stale or disposed work cannot publish, and no file-sized enhancement can monopolize the main thread. Add phase attribution for validation/model/build/projection/attachment/intraline/syntax/refresh; focused DOM tests; the exact large-comparison browser fixture/gate; spec and performance guidance reconciliation. Acceptance: exact route and revision navigation preserve one mounted comparison and exact convergence, initial DOM stays proportional to visible rows, expansion works in unified/split, no >200 ms task/frame or page exception on repeated headed runs, make format and make verify pass.

## Notes

Implemented and delivered Phase 5 through the full stack. Collapsed changed runs mount only the 20-row visible prefix, expand in cancellable 100-row tasks, release row DOM and text hosts on collapse, and cancel on layout reprojection, navigation replacement, or disposal. One-sided runs bypass alignment caches. JSON decode, validation, model construction, per-file projection, whole-comparison projection, and DOM attachment are independently attributed. The standard performance profile now hard-fails unless collapsed_diff_rows_materialized is zero. Exact 10-file, 19,654-line, 1.26 MB control/candidate evidence: 182,686 to 6,476-6,679 DOM nodes; 552 ms to 127 ms longest task; two to zero tasks over 200 ms; 507 ms to 78 ms maximum attributed frame blocking; zero collapsed hidden rows and no page/render errors. Focused 63-test suite, make format, make verify with 1,561 tests and 48 golden scenarios, pre-commit, and pre-push pass. Pushed as b5929e7 on PR #81, merged through PR #82 as 5caa1e0 and PR #84 as 0bd3d5b. PR #81 and PR #82 exact heads are green. Final headed git-revisions scenario on 0bd3d5b passed exact convergence, zero blank frames, one mount, bounded/cancelled hydration, Files-Git state recovery, zero exceptions, 88 ms maximum Long Task, and no blocking frame over 200 ms. Exact large comparison on the globally installed metab 0.7.2.dev44+0bd3d5b has 195 visible rows, zero collapsed rows, 6,320 DOM nodes, and no main-thread warning; remaining latency was server-side diff/tree delivery.
