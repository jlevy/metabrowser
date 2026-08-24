---
title: The v0.6.0 regression leaves one visual regression
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-013
  title: The v0.6.0 regression leaves one visual regression
  date: "2026-08-23"
  hypotheses:
    - H58
    - H11
  subject:
    corpus: ten project-shaped trees cloned from the locked development installs
    corpus_files: 111590
    corpus_dirs: 6520
    host_system: Darwin 25.5.0
    browser: Chromium in the visible in-app browser
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: globally installed v0.6.0 at tag v0.6.0
    candidate: installed wheel from PR head 62759c1
    record: devtools comparator output, serving JSON, and six ignored .bench browser profiles summarized below
  results:
    - metric: backend_first_row_s
      control_median: 4.415
      candidate_median: 1.395
      control_range: [2.63, 4.587]
      candidate_range: [1.205, 1.522]
      change_pct: -68.4
      overlapping: false
    - metric: backend_index_done_s
      control_median: 44.672
      candidate_median: 16.79
      control_range: [39.796, 50.361]
      candidate_range: [15.719, 20.391]
      change_pct: -62.4
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 664
      candidate_median: 322
      control_range: [542, 700]
      candidate_range: [256, 341]
      change_pct: -51.5
      overlapping: false
    - metric: browser_tree_fetch_total_ms
      control_median: 263
      candidate_median: 21
      control_range: [87, 274]
      candidate_range: [20, 28]
      change_pct: -92.0
      overlapping: false
    - metric: browser_long_task_max_ms
      control_median: 5963
      candidate_median: 0
      control_range: [0, 6280]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: true
    - metric: browser_main_thread_blocked_pct
      control_median: 31.4
      candidate_median: 0
      control_range: [0, 33]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: true
    - metric: browser_tree_region_repaints
      control_median: 1
      candidate_median: 2
      control_range: [1, 1]
      candidate_range: [2, 2]
      change_pct: 100.0
      overlapping: false
    - metric: scanning_rollup_p50_ms
      control_median: 1.15
      candidate_median: 4.2
      control_range: [1.1, 1.2]
      candidate_range: [4.1, 4.3]
      change_pct: 265.2
      overlapping: false
    - metric: browser_js_heap_mb
      control_median: 11.8
      candidate_median: 14.9
      control_range: [11.8, 13.3]
      candidate_range: [14, 17]
      change_pct: 26.3
      overlapping: false
  complexity:
    new_dependencies: []
    new_failure_modes:
      - an external benchmark can be mislabeled unless the harness resolves its executable and records an immutable build reference
      - in-app browser automation emits untrusted events, so it cannot satisfy the real-interaction evidence gate
    notes: >-
      The reusable harness now resolves and versions the selected console script,
      requires a build reference for external browser runs, accepts exported profile
      files, and resolves the corpus before benchmark subprocesses change directory.
      No product dependency or compatibility layer was added.
  verdict:
    decision: unresolved
    primary_metric: hard responsiveness gates plus the full non-regression matrix
    reason: >-
      The candidate removes the release's multi-second freezes in all three observed
      runs and is materially faster to rows, tree data, and index completion. It is
      not strictly better on every metric: the tree is still replaced twice, scanning
      rollup requests take about three additional milliseconds, and the retained
      browser heap is about three megabytes larger. The browser controller also cannot
      produce the trusted input required for an admissible interaction result. H11 and
      one physical-input pass therefore remain before the strict acceptance claim.
---
# The v0.6.0 regression leaves one visual regression

## Question

Does the current pull request make the large-tree experience strictly better than the
installed `v0.6.0` release across backend delivery, loading, responsiveness, stability,
resources, and memory?

The short answer is no, under that literal criterion.
The current build is much faster and avoids the release’s intermittent multi-second
browser freezes, but the full matrix catches a second tree paint, a small scanning-route
latency increase, and a bounded heap increase.

## Build provenance

The control is the globally installed uv-tool console script, which reports
`metab 0.6.0`. Its `app.js` SHA-256 matches the file at tag `v0.6.0`, commit
`440a2fe3a8050ce3dbd85c117d012fb8823a73b4`. The candidate is a wheel built from
pull-request head `62759c1`, installed into a fresh throwaway environment; it reports
`metab 0.6.1.dev55+62759c1`.

The release predates the navigation-time profiler.
For the browser half only, a temporary copy of the installed release package replaced
its old recorder with the current one and connected that recorder to the old public
namespace. The old application and server files remained byte-identical.
Both builds received the same fixed 60-second profile exporter, so the observation
window and instrumentation overhead match.
None of that temporary instrumentation ships in the product.

## Corpus and method

The corpus contains ten copies of a project-shaped tree assembled from this repository’s
locked installs.
The corpus builder reports 247,062 physical files in 31,201 directories;
the inventory’s visibility rule admits 111,590 files in 6,520 directories.
Every comparison used the same corpus, machine, executable form, and 1600×900 visible
browser viewport.

The backend comparator alternated five control and candidate runs.
It fingerprinted the corpus before and after, compared the ordered navigation rows and
tallies, and refused timing results until those answers were equivalent.
The serving matrix was then run in both orders, and the unattached scan received four
additional alternating pairs.

The browser half retained three cold profiles per build.
Each profile began with the document and exported at 60 seconds, after the inventory
settled. All six stayed visible, reached `index_status_at_probe=done`, supported the
required Long Task and Event Timing observers, and retained their full resource and
label buffers.

## Backend result

The five-run semantic comparator passed with no row or tally differences and an
unchanged corpus.

| measure | v0.6.0 median (range) | PR median (range) | result |
| --- | ---: | ---: | --- |
| process to serving | 0.733 s (0.679–0.814) | 0.794 s (0.679–1.787) | no detected difference |
| first navigation row | 4.415 s (2.630–4.587) | **1.395 s (1.205–1.522)** | 3.2× faster |
| index complete | 44.672 s (39.796–50.361) | **16.790 s (15.719–20.391)** | 2.7× faster |
| peak RSS | 182.1 MB (181.5–185.2) | 178.6 MB (177.4–186.1) | no detected difference |

The first unattached serving sample put the candidate 5.6% behind.
Four more alternating pairs did not reproduce that ordering.
Across all five samples, the release median was 19.180 seconds and the candidate median
was 16.235 seconds; their ranges overlap, so the conclusion is no proven regression, not
a claimed 15% win.

The two-run serving matrix shows the important delivery split:

| measure | v0.6.0 median | PR median | result |
| --- | ---: | ---: | --- |
| scan with polling client | 38.65 s | **34.90 s** | 9.7% faster; ranges overlap |
| first folder count | 7.110 s | **2.475 s** | 2.9× faster |
| root tree, depth 1 | 6.00 ms | **3.25 ms** | 46% faster |
| root tree, depth 2 | 6.80 ms | **3.95 ms** | 42% faster |
| rollup during scan, p50 | **1.15 ms** | 4.20 ms | candidate 3.05 ms slower |
| rollup during scan, p95 | **9.65 ms** | 12.40 ms | candidate 2.75 ms slower |
| retained rollup body | 3.60 ms | **3.25 ms** | candidate 0.35 ms faster |
| eight simultaneous clients | 12.10 ms | 12.20 ms | no detected difference |

The scanning-rollup delta is real but not a responsiveness explanation: both conditions
are under 13 ms at p95, while the candidate completes the contended scan sooner.
It remains a performance dimension to preserve and improve rather than a number to hide
inside the faster total.

## Browser result

The candidate is faster on the reader’s critical path:

| measure | v0.6.0 median (range) | PR median (range) |
| --- | ---: | ---: |
| first row | 664 ms (542–700) | **322 ms (256–341)** |
| initial tree fetch | 263 ms (87–274) | **21 ms (20–28)** |
| first contentful paint | 256 ms (108–1,852) | **136 ms (128–144)** |
| largest contentful paint | 732 ms (392–1,852) | **404 ms (360–472)** |
| reserved-region movement | 77 px | **52 px** |
| subtree requests | 32 | **23** |

Responsiveness is the decisive difference.
The candidate recorded no Long Task and no animation frame over 200 ms in any of its
three runs. Two of the three release runs recorded 19 and 24 long tasks; their worst
tasks were 6,280 and 5,963 ms, and they blocked the main thread for 31.4% and 33.0% of
the fixed window. The third release run happened not to enter that event pattern and
recorded none.
That variability is why the gate checks every run: a clean median or lucky
reload may not excuse one user-visible freeze.

## Wrong-way browser metrics

The browser result is not a universal Pareto improvement.

- `tree_region_repaints` is 1 in every release run and 2 in every candidate run.
  The server inlines the first rows, then the client replaces the whole panel with the
  fetched snapshot. H11 (`mb-izxl`) already names this regression and its target of one
  paint.
- JavaScript heap at 60 seconds has a non-overlapping median increase from 11.8 MB to
  14.9 MB. The absolute value is small, but it is a retained-memory tradeoff and must
  not be called an improvement.
- Script and style transfer grow by about 4 KB; total transfer medians overlap because
  the release’s progressive API traffic varies by more than that.
- The candidate’s median CLS is lower, 0.0017 versus 0.0044, but it emits more shift
  entries and one run reaches 0.0091. Both are well under the 0.1 target; the mixed
  directions do not support a strict-better claim.

## Interaction evidence limitation

The in-app browser’s automation APIs dispatch clicks with `isTrusted=false`. The
recorder correctly excluded them, and `run.py record --json-file` rejected the profiles
with `no trusted pointer or keyboard interaction was captured during the run`. The
controlled click wall time is useful while debugging, but it is not an admissible Event
Timing or INP sample and is not reported as one here.

The loading, Long Task, animation-frame, layout, resource, and memory observations are
still navigation-time browser measurements; they do not depend on the click.
A final physical-input pass remains necessary for the interaction budget itself.

## Regression coverage added

The failed first benchmark attempt found another silent provenance hazard.
The serving harness previously selected whichever `metab` appeared first on `PATH`, and
the browser harness always launched the current environment through `uv`. They could not
honestly compare installed artifacts.

The reusable framework now:

- resolves and versions the exact console script before a serving run;
- requires `--build-ref` when a browser run selects an external executable;
- records the selected build version with browser evidence;
- accepts exported profiles through `record --json-file`;
- resolves a relative corpus before the comparator launches servers from `/tmp`; and
- tests each of those contracts.

The comparator bug matters beyond this round: it had turned a valid relative corpus into
a nonexistent `/tmp` path and reported ten symmetric server exits.
The new regression test reproduces that working-directory boundary.

## Verdict

**Unresolved under the requested strict all-metrics criterion.**

The main concern that opened the pull request is fixed: a faster producer no longer
makes the browser sluggish, and the candidate is materially faster to useful content
than `v0.6.0`. The current data do not justify saying every performance metric is
better. H11’s second tree paint and a physical trusted-interaction pass remain before
that claim; the scanning-rollup and heap deltas should stay visible as bounded
tradeoffs.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
