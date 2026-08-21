---
type: is
id: is-01m0k5xdka0fyb19aw97wg5v7s
title: "Add a page-load phase to bench_serving.py: FCP, DCL, time to first tree row"
kind: task
status: open
priority: 0
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k5xdzw6kmhd49gfyxjhwhx
  - type: blocks
    target: is-01m0k4p13yqdg3yp2c78rawbhz
  - type: blocks
    target: is-01m0k5xec4q8565zxfs4mr4dsy
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:56.425Z
updated_at: 2026-08-21T22:48:26.930Z
---
Extend devtools/bench_serving.py with a page-load phase. It already builds the corpus, starts metab, parses the banner for the port it settled on, waits on the walker's completion log line, and writes a labelled result JSON that --baseline diffs. What it has never measured is paint.

Needs a real browser, which this repository does not currently depend on. Deciding how to get one is part of this bead, not a detail: adding Playwright is a supply-chain change under the 14-day cool-off, and the existing precedent (docs/e2e-testing.md) is that Node-backed tests skip when Node is absent. A phase that records {"skipped": "<reason>"} when no driver is present would match that precedent.

Measure two page loads, because they answer different questions and averaging them answers neither:
  cold    - opened right after the server starts, walk still running. This is what a reader gets on first open and it is the 4.5 s / 22 s number.
  settled - opened after the walk converges. Isolates render cost from scan cost.

Definitions, which must match the ones already recorded in the spec or the numbers will not be comparable:
  FCP                     performance.getEntriesByType('paint'), first-contentful-paint entry startTime
  DOMContentLoaded        navigation entry domContentLoadedEventEnd
  load                    navigation entry loadEventEnd
  time to first tree row  wall clock from navigation commit until a [role="treeitem"] element exists
  rendered rows           document.querySelectorAll('[role="treeitem"]').length
  DOM nodes               document.querySelectorAll('*').length
  transferred             sum of transferSize over resource entries (compressed)

Navigate /view/ for tree measurements and /view/README.md for document ones. Median of at least five cold loads, each in a fresh browser context so no module or HTTP cache carries over.

Time to first row is the measure a naive harness gets wrong: waiting for load reports a page that painted its shell, and waiting for network idle reports a scan that finished. Neither is when the reader can use the tree.

Fold the rows into _rows() so one --baseline comparison covers serving and page load together.
