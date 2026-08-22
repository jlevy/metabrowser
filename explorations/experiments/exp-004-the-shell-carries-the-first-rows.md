---
title: The shell carries the tree's first rows
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-004
  title: The shell carries the tree's first rows
  date: "2026-08-22"
  hypotheses:
    - H20
  subject:
    corpus: devtools/bench_serving.py build_corpus
    corpus_files: 300000
    corpus_dirs: 972
    host_system: Darwin 25.5.0
    browser: Chromium
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: false
    control: the tree paints when the first /api/tree fetch returns
    candidate: the index handler inlines the root's depth-1 rows, the client paints them at DOMContentLoaded, and the fetch reconciles
    record: explorations/results/runs.jsonl
  results:
    - metric: first_row_ms
      control_median: 1604
      candidate_median: 242
      control_range: [1447, 2200]
      candidate_range: [232, 326]
      change_pct: -84.9
      overlapping: false
    - metric: long_task_ms_total
      control_median: 268
      candidate_median: 65
      control_range: [191, 372]
      candidate_range: [63, 82]
      change_pct: -75.7
      overlapping: false
    - metric: transferred_kb
      control_median: 518
      candidate_median: 552
      control_range: [517, 521]
      candidate_range: [550, 553]
      change_pct: 6.6
      overlapping: false
    - metric: load_tree_ms
      control_median: 1411
      candidate_median: 1052
      control_range: [1248, 1828]
      candidate_range: [924, 1403]
      change_pct: -25.4
      overlapping: true
  complexity:
    lines_changed: 74
    new_dependencies: []
    new_failure_modes:
      - "The inlined rows are a snapshot taken at page-render time. They are painted once, never reconciled against, and replaced wholesale by the fetch that follows; a reader can see rows a moment out of date before that lands."
      - "Only the unfiltered default view is inlined. A filter or a recency source skips the inline entirely rather than painting rows that do not describe it."
    notes: One block in the index handler, one function in app.js, one call at the top of loadTree. No protocol change and no new request.
  verdict:
    decision: accepted
    primary_metric: first_row_ms
    reason: "1,604 ms to 242 ms on ranges that do not overlap, at n=3 each -- the tree is now usable at DOMContentLoaded instead of one slow round trip later. Main-thread blocking fell with it, 268 ms to 65 ms, also non-overlapping. The cost is 34 KB more transferred, which is the inline payload plus the thirteen now-visible folders the viewport sweep warms; that is the trade and it is a good one."
---
# The shell carries the tree’s first rows

## Hypothesis

**H20.** Time to first row is `DOMContentLoaded` plus the whole `/api/tree` round trip.
The server could have answered the first part of that request before the browser asked:
the root’s immediate children are in the warm index, and the shell it is already
rendering has room to carry them.
Inline them, paint at DCL, and let the fetch reconcile.

Predicted: `first_row_ms` collapses to roughly FCP plus render time, in both scan
regimes.

The metric named before measuring was `first_row_ms`.

## Why this experiment exists

[exp-003](exp-003-navigation-tallies-on-a-staleness-bound.md) made the root route 40%
faster during a scan and moved time to first row not at all — the first request of a
page load misses a cold cache by construction, so it pays the full cost no matter what
the cache policy is.
That result is what promoted this hypothesis from “independent” to “necessary”: the only
way to stop the reader waiting for that request is to not make them wait for it.

## What was tried

The index handler builds the root at depth 1 off the warm index and inlines it as
`window.METABROWSER_INITIAL_TREE`, capped at 200 rows.
`loadTree` paints those rows before it sends its fetch, then proceeds exactly as before.

Three constraints shaped it more than the mechanism did:

**Bounded, because it rides in the HTML.** Every inlined byte is on the critical path
for every reader, including one whose root holds ten thousand entries.
Two hundred rows is past any viewport at any sane row height, so the cap costs nothing a
reader can see and stops the shell growing with the tree.

**Unfiltered only.** A filter is client state the server has not been told about when it
renders the page, so inlining a filtered view would paint rows the reader’s filter
excludes. The inline checks `treeFilterKey()` — the same key the request carries — and
declines when anything is set.

**Painted once, and not authoritative.** The rows are a snapshot from page-render time.
They are consumed on first use and the cache slot is cleared immediately, so the fetch
that follows replaces them wholesale rather than merging into them.
A second paint from a stale snapshot would be a regression dressed as a shortcut.

## What the numbers said

| metric | control (n=3) | candidate (n=3) |
| --- | --- | --- |
| `first_row_ms` | 1,604 (1,447–2,200) | **242 (232–326)** |
| `long_task_ms_total` | 268 (191–372) | **65 (63–82)** |
| `transferred_kb` | 518 (517–521) | 552 (550–553) |
| `load_tree_ms` | 1,411 (1,248–1,828) | 1,052 (924–1,403) |

**The tree is usable at `DOMContentLoaded`.** `first_row_ms` tracks `dcl_ms` almost
exactly in the candidate — 232 against 233, 242 against 243, 326 against 329 — which is
the prediction stated as an identity rather than a number.
The thirteen rows render in 1–2 ms.

**Main-thread blocking fell too, and that was not predicted.** 268 ms to 65 ms on
non-overlapping ranges.
The likely reason is that the small inline render happens while the thread is idle, and
the full render lands later against less competition, but this experiment did not
isolate it and the claim is only that it moved.

`load_tree_ms` looks better and is not claimed: the ranges overlap, and nothing in this
change makes the fetch itself faster.

## The cost

**34 KB more transferred**, on non-overlapping ranges, and it is worth naming rather
than rounding away. Part is the inline payload.
The larger part is thirteen `/api/tree?path=` requests that the control never made: the
inlined rows are on screen, so the viewport-bounded sweep from
[exp-002](exp-002-subtree-prefetch-bounded-to-the-viewport.md) correctly warms them.
That is the sweep doing its job a second earlier, not a leak — the control warmed
nothing on load only because it had nothing on screen to warm.

## Limitations

One corpus, one machine, n=3 per condition, and a root of thirteen entries.
A root with several thousand immediate children would exercise the 200-row cap, which
nothing here measures.
The reconciliation path is exercised only in the case where the inlined rows and the
fetched rows agree; a tree changing under the reader between page render and fetch is
untested. And `fcp_ms` is still null in this pane, so “usable at DCL” is anchored to
`DOMContentLoaded` rather than to paint.

## Verdict

**ACCEPTED on `first_row_ms`,** 1,604 ms → 242 ms, with main-thread blocking 268 ms → 65
ms, both on non-overlapping ranges, for 34 KB.

This is the change H8 was originally credited with being able to make.
The route being slow during a scan was real; the reader waiting on it was the part that
could be fixed without making the route fast.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
