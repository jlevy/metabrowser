---
title: Rows stop waiting for the tally pass
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-007
  title: Rows stop waiting for the tally pass
  date: "2026-08-22"
  hypotheses:
    - H27
    - H31
  subject:
    corpus: build_project_corpus at 10 projects (246,282 files, 31,161 directories), with two real working trees as sanity checks
    corpus_files: 246282
    corpus_dirs: 31161
    host_system: Darwin 25.5.0
    browser: n/a
    viewport: "n/a"
    cold: true
  method:
    runs_per_condition: 2
    interleaved: true
    control: one response carries both the rows and the navigation tallies
    candidate: a row request serves tallies only from a fresh memo; depth=0 is the channel that computes them, fetched by the client after the render
    record: explorations/performance-loop/results/runs.jsonl
  results:
    - metric: srv_scanning_ms
      control_median: 311
      candidate_median: 2
      control_range: [292, 330]
      candidate_range: [2, 2]
      change_pct: -99.4
      overlapping: false
    - metric: srv_scanning_ms_real_tree_a
      control_median: 777
      candidate_median: 6
      control_range: [0, 1446]
      candidate_range: [0, 10]
      change_pct: -99.2
      overlapping: false
    - metric: srv_scanning_ms_real_tree_b
      control_median: 67
      candidate_median: 1
      control_range: [10, 124]
      candidate_range: [1, 1]
      change_pct: -98.5
      overlapping: false
    - metric: walk_elapsed_ms_attached_real_tree_a
      control_median: 70211
      candidate_median: 49960
      control_range: [70211, 70211]
      candidate_range: [49960, 49960]
      change_pct: -28.8
      overlapping: false
    - metric: srv_settled_ms
      control_median: 3
      candidate_median: 4
      control_range: [3, 3]
      candidate_range: [3, 4]
      change_pct: 33.3
      overlapping: true
  complexity:
    lines_changed: 61
    new_dependencies: []
    new_failure_modes:
      - "Filter counts arrive a beat after the rows on a first load. Every tally field was already nullable and guarded field-by-field on the client, and the summary row already had a fallback, so this is a shape the browser handled before the change."
    notes: One branch in the tree route, one call in loadTree, and the in-process --check-api probe taught to ask both channels.
  verdict:
    decision: accepted
    primary_metric: srv_scanning_ms
    reason: "311 ms to 2 ms on the official corpus, 777 ms to 6 ms and 67 ms to 1 ms on the two real trees, all non-overlapping. The walk under a client also fell 70.2 s to 50.0 s on the largest tree, which is the contention loop of H31 weakening: the request cost was what stole CPU from the walker, so removing it gave the scan back a third of its time."
---
# Rows stop waiting for the tally pass

## Hypothesis

**H27.** The tallies behind the navigation filters cost one visit per entry in the
index. The rows do not.
They shared one response, so a reader waited for the expensive half in order to see the
cheap one — and [exp-003](exp-003-navigation-tallies-on-a-staleness-bound.md) had
already shown that bounding the recompute helps every request except the first, which is
the one a reader waits on.

[exp-005](exp-005-a-real-tree-changes-the-priorities.md) then showed the wait is not
only the reader’s. That pass competes with the walker, so watching a scan made it twelve
times slower. The per-request cost is the input to that loop.

The metric named before measuring was `srv_scanning_ms` — the server’s own share of a
row request while the walk runs.

## What was tried

A row request now serves tallies **only if they are already memoized**, and never
computes them. `depth=0` is the channel that is allowed to pay: it carries no rows to
delay, and `scheduleRootSummaryRefresh` — which already existed — fetches it behind the
render and applies both the tallies and the summary row.

The change was close to a payload-shape change, as predicted.
Every tally field in the response was already nullable, `updateFilterTallies` already
guarded each one with `Array.isArray`, and `treeSummaryHtml` already had a fallback for
a missing summary. The browser handled a tally-less response before this experiment;
nothing had ever sent one.

One consumer did need teaching.
The in-process `metab --check-api` navigation probe validates the tree envelope and
expects a summary in it, so it now asks both channels — which is what the browser does.

## What the numbers said

`probe-server` sampling `/api/tree?depth=2`, the row request the client actually makes,
across a whole scan and again once settled.

| tree | control | candidate |
| --- | ---: | ---: |
| **official corpus** (246,282 files) | 311 ms (292–330) | **2 ms (2–2)** |
| **real tree A** (241,063 files) | 777 ms (0–1,446) | **6 ms (0–10)** |
| **real tree B** (320,064 files) | 67 ms (10–124) | **1 ms (1–1)** |

Settled cost is unchanged at 3–4 ms, which is the point: nothing was made faster, the
expensive work was moved off the path that did not need it.

### The loop gave back a third of the scan

Unpredicted, and the more interesting number:

|  | walk elapsed, one client attached |
| --- | ---: |
| control | 70.2 s |
| candidate | **50.0 s** |

The row requests were not only slow, they were *taking* something.
Each one spent most of a second of CPU that the walker wanted, under a GIL they share.
Remove the cost and the scan finishes 29% sooner without touching the walker at all.
That is
[H31](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses)’s
feedback loop measured from the other end.

## Where the real tree now stands

Three rounds have touched this tree, and it is worth stating cumulatively, because no
single experiment shows it:

|  | before exp-006 | now |
| --- | ---: | ---: |
| gitignore build, before any row can exist | 21.4 s | **2.2 s** |
| row request during a scan | 777 ms | **6 ms** |
| walk with a client attached | 258 s | **50 s** |

## Limitations

Two runs per condition on the official corpus and one on each real tree — enough for a
150× effect and nothing subtler.
The walk-elapsed comparison is n=1 per side; the direction is unambiguous and the
magnitude is not pinned.
`srv_scanning_ms` is the server’s own share from `Server-Timing`, so it excludes client
queueing.

Nothing here was measured in a browser.
The reader-facing consequence — that the filter counts now arrive a beat after the rows
— is a real change in what the page does over time, and only its *mechanism* is
verified: the fields were already nullable and already guarded.
A browser round on a real tree would be the honest confirmation and has not been run.

## Verdict

**ACCEPTED on `srv_scanning_ms`**, 311 ms → 2 ms on the official corpus with both real
trees agreeing, and a 29% shorter attached scan as a consequence nobody asked for.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
