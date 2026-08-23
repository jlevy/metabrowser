---
title: Every checkpoint on one corpus
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-010
  title: Every checkpoint on one corpus
  date: "2026-08-22"
  hypotheses:
    - H55
    - H53
  subject:
    corpus: build_project_corpus at 10 projects, held fixed while src/metabrowser moved
    corpus_files: 246282
    corpus_dirs: 31161
    host_system: Darwin 25.5.0
    browser: Chromium
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: false
    control: src/metabrowser at 405bf31, the merge before the performance campaign began
    candidate: src/metabrowser at 61ed8e0, the head of this branch
    record: explorations/performance-loop/results/runs.jsonl
  results:
    - metric: first_row_ms
      control_median: 1473
      candidate_median: 276
      control_range: [1473, 1473]
      candidate_range: [213, 533]
      change_pct: -81.3
      overlapping: false
    - metric: tree_fetch_srv_ms
      control_median: 1099
      candidate_median: 6
      control_range: [1099, 1099]
      candidate_range: [3, 8]
      change_pct: -99.5
      overlapping: false
    - metric: last_resource_ms
      control_median: 28865
      candidate_median: 12276
      control_range: [28865, 28865]
      candidate_range: [11074, 16751]
      change_pct: -57.5
      overlapping: false
    - metric: subtree_requests
      control_median: 32
      candidate_median: 23
      control_range: [32, 32]
      candidate_range: [23, 23]
      change_pct: -28.1
      overlapping: false
    - metric: reserved_region_shift_px
      control_median: 42
      candidate_median: 23
      control_range: [42, 42]
      candidate_range: [23, 23]
      change_pct: -45.2
      overlapping: false
    - metric: tree_region_repaints
      control_median: 1
      candidate_median: 3
      control_range: [1, 1]
      candidate_range: [3, 3]
      change_pct: 200.0
      overlapping: false
  complexity:
    lines_changed: 0
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      No product change. The sweep swaps src/metabrowser to each checkpoint and
      leaves the corpus, the harness and the probe at today's version, which is
      the separation the fixed corpus exists to make possible.
  verdict:
    decision: baseline
    primary_metric: first_row_ms
    reason: "The campaign is worth what it claimed on the metrics it aimed at and cost something on two it did not. Time to first row 1,473 ms to 276, the server's own share of the first tree fetch 1,099 ms to 6, the request tail 28.9 s to 12.3. Against that: the tree region is painted three times where it was painted once, and the page's downward shift went 42 px to 67 before this branch took it to 23, so main today moves the reader further than the code did before any of this work started. Both regressions were introduced by accepted rounds and neither was visible until every checkpoint sat on one corpus."
---
# Every checkpoint on one corpus

## Why this round exists

Forty-eight recorded runs, seven corpora: `.bench/corpus-300000`, two synthetic sizes
recorded before the corpus was labelled at all, `tree-585f5500`, two revisions of
`tree-a01f4187`, and `tree-e167d99b`.

Each round measured its own control against its own candidate on whatever tree was
current, which is sound *per round* and is why every verdict so far stands.
What it cannot do is answer the question a reader actually asks — *what did all of this
buy?* — because no two rounds share a scale.
`report.md` says as much in the line above its own tables: conditions are grouped by
corpus, because none of these numbers compare across one.

This round answers it, using the property the fixed corpus was built for: hold the
corpus and the eval harness at today’s version and move only `src/metabrowser`.

## Method

Four checkpoints, chosen as the merges that bracket the performance work and named by
the round whose change they carry:

| label | commit | what it is |
| --- | --- | --- |
| `p0-before-perf` | `405bf31` | the merge before the campaign began |
| `p1-rows-partial-index` | `b9420c1` | rows served from a partial index (exp-004) |
| `p2-main` | `9084e6b` | current `main`, carrying the subtree sweep and the gitignore pruning (exp-002, exp-006, exp-007) |
| `p3-skeleton-paint` | `61ed8e0` | this branch (exp-009) |

Each was served from the same 246,282-file corpus on a fresh port — a port is part of
the origin, so a new one is an empty HTTP cache and a scan still running — and probed
with today’s `probe.js` at 1280×900.

`p2` and `p3` were run three times each.
`p0` and `p1` were run once, which is enough for effects of this size and is stated here
rather than buried: the smallest claim made about them is a fivefold difference, and the
widest variance the replicated conditions showed is well inside that.

## What the campaign bought

| metric | `p0` before | `p1` | `p2` main | `p3` this branch |
| --- | ---: | ---: | ---: | ---: |
| `first_row_ms` | 1,473 | 1,031 | 294 | **276** |
| `tree_fetch_srv_ms` | 1,099 | 735 | 5 | **6** |
| `last_resource_ms` | 28,865 | 25,012 | 10,272 | **12,276** |
| `subtree_requests` | 32 | 32 | 23 | **23** |

Time to a usable tree fell by a factor of five, and the server’s own share of the first
tree request by a factor of nearly two hundred — from a second of work before it could
answer at all, to single-digit milliseconds.
The request tail, which is what keeps a large tree busy long after it looks finished,
more than halved.

## What it cost

Two metrics moved the wrong way, and neither was visible from inside the rounds that
caused them.

**The tree region is painted three times where it was painted once.** `p0` and `p1`
render it exactly once; `p2` and `p3` render it three times — inlined rows, fetched
rows, refresh.
exp-004 bought its first-row win by painting from the inlined payload, and
the payment is a page assembled in front of the reader.
That is
[H53](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses),
with
[H11](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses)
— patch the panel rather than replacing it — as the fix.

**`main` today moves the reader further than the code did before any of this work
started.**

|  | `p0` | `p1` | `p2` main | `p3` this branch |
| --- | ---: | ---: | ---: | ---: |
| `filter_bar_shift_px` | 24 | 24 | 24 | **0** |
| `summary_shift_px` | 18 | 18 | 43 | **23** |
| `reserved_region_shift_px` | 42 | 42 | **67** | **23** |

The filter bar has cost 24 px since before the campaign.
The tally row cost 18 px until the split row — tracked and ignored counted separately —
landed on main, at which point its text became long enough to wrap to a second line in a
300 px navigation pane and the cost became 43.

Nobody measured it, because until exp-009 there was no metric that would have noticed.
A feature that reads as pure gain in a wide window is a 25 px regression in a narrow
one, and the loop had no way to see it.
This branch nets it to 23 px, better than the pre-campaign baseline but not zero; the
remainder is
[H54](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses).

## What this round does not show

**`p2` against `p3` is not a result on the timing metrics, and is not claimed as one.**
`first_row_ms` reads 294 (207–311) against 276 (213–533): the ranges overlap heavily,
and there is no mechanism by which two `min-height` declarations and one changed render
argument would move it.
The accept rule says an overlap is not a result, and it is not being treated as one
here.

The shift metrics are the opposite case — 67 against 23, zero variance across three runs
each, because they are layout facts rather than timings.

**One corpus, one machine, one viewport, and the shift figures are pane-width
dependent** — the tally row wraps at 300 px and would not at 600. `lcp_ms` and `cls` are
null throughout for the reason exp-009 records: this pane is never visible, so Chromium
never computes them.
That is H51.

**These are cold loads of a settling tree.** Nothing here describes using the thing —
interaction latency, churn recovery, resident size, warm reopen — which is H49, still
the largest unmeasured area in the plan.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
