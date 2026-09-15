---
title: The quiet-machine v0.10.0 comparison rejects the candidate on the 300k corpus
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-034
  title: The quiet-machine v0.10.0 comparison rejects the candidate on the 300k corpus
  date: "2026-09-15"
  hypotheses: []
  subject:
    corpus: >-
      repository-shaped project-10 tree-8cf3e743 (118,860 walker-visible files of 254,602
      on disk, 6,770 directories, built at 03fd7997) and synthetic build_corpus shape 2
      tree-138d8520 (300,000 files, 1,104 directories)
    corpus_files: 118860
    corpus_dirs: 6770
    host_cpu: Intel Xeon @ 2.80GHz, 4 vCPU
    host_system: Linux 6.18.44-fc-v24, CPython 3.13.12 standard build
    browser: headed Chromium 141 driven through the DevTools Protocol on an Xvfb screen
    viewport: "1600x1040"
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: exact installed v0.9.1 wheel built from tag commit 16211ccb
    candidate: exact installed wheel built from 03fd7997, the v0.10.0 release candidate
    record: >-
      runs.jsonl labels exp-034-p10-release-v091, exp-034-p10-candidate-03fd7997,
      exp-034-300k-release-v091 and exp-034-300k-candidate-03fd7997, five captures per
      condition per corpus in the order C K K C C K K C C K, one environment alternating
      only the Metabrowser wheel; plus five compare_builds pairs per corpus. The 1.3x
      back-to-back pair rule, on a quiet host
  results:
    - metric: project10_browser_first_row_ms
      control_median: 1238
      candidate_median: 230
      control_range: [1189, 1392]
      candidate_range: [198, 317]
      change_pct: -81.4
      overlapping: false
    - metric: project10_browser_walk_elapsed_ms
      control_median: 39203
      candidate_median: 15507
      control_range: [38741, 40442]
      candidate_range: [15100, 16758]
      change_pct: -60.4
      overlapping: false
    - metric: project10_browser_tree_fetch_srv_ms
      control_median: 1
      candidate_median: 39
      control_range: [1, 3]
      candidate_range: [9, 44]
      change_pct: 3800.0
      overlapping: false
    - metric: project10_browser_js_heap_mb
      control_median: 8
      candidate_median: 24
      control_range: [8, 9.6]
      candidate_range: [21.4, 26.6]
      change_pct: 200.0
      overlapping: false
    - metric: project10_browser_js_heap_after_gc_mb
      control_median: 6.1
      candidate_median: 6.4
      control_range: [6.1, 6.2]
      candidate_range: [6.4, 6.4]
      change_pct: 4.9
      overlapping: false
    - metric: project10_browser_interaction_max_ms
      control_median: 40
      candidate_median: 32
      control_range: [16, 40]
      candidate_range: [32, 48]
      change_pct: -20.0
      overlapping: true
    - metric: project10_browser_long_task_max_ms
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: project10_browser_fcp_ms
      control_median: 1140
      candidate_median: 188
      control_range: [1084, 1260]
      candidate_range: [144, 316]
      change_pct: -83.5
      overlapping: false
    - metric: project10_backend_first_row_s
      control_median: 5.806
      candidate_median: 0.016
      control_range: [2.911, 6.233]
      candidate_range: [0.014, 0.019]
      change_pct: -99.7
      overlapping: false
    - metric: project10_backend_index_done_s
      control_median: 39.193
      candidate_median: 9.315
      control_range: [35.933, 40.799]
      candidate_range: [8.74, 9.393]
      change_pct: -76.2
      overlapping: false
    - metric: project10_backend_peak_rss_mb
      control_median: 187.4
      candidate_median: 187.4
      control_range: [187.2, 187.5]
      candidate_range: [187.2, 187.7]
      change_pct: 0.0
      overlapping: true
    - metric: project10_backend_tally_overlap_progress_max_ms
      control_median: 80.6
      candidate_median: 77.6
      control_range: [50.0, 95.7]
      candidate_range: [72.5, 158.7]
      change_pct: -3.7
      overlapping: true
    - metric: synthetic300k_browser_first_row_ms
      control_median: 293
      candidate_median: 359
      control_range: [282, 312]
      candidate_range: [312, 392]
      change_pct: 22.5
      overlapping: false
    - metric: synthetic300k_browser_walk_elapsed_ms
      control_median: 18715
      candidate_median: 31295
      control_range: [17777, 18845]
      candidate_range: [28852, 33022]
      change_pct: 67.2
      overlapping: false
    - metric: synthetic300k_browser_tree_fetch_srv_ms
      control_median: 6
      candidate_median: 22
      control_range: [6, 9]
      candidate_range: [12, 32]
      change_pct: 266.7
      overlapping: false
    - metric: synthetic300k_browser_lcp_ms
      control_median: 180
      candidate_median: 416
      control_range: [148, 220]
      candidate_range: [360, 464]
      change_pct: 131.1
      overlapping: false
    - metric: synthetic300k_browser_last_resource_ms
      control_median: 22281
      candidate_median: 35139
      control_range: [21160, 22476]
      candidate_range: [33131, 37122]
      change_pct: 57.7
      overlapping: false
    - metric: synthetic300k_browser_long_task_max_ms
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 98]
      overlapping: true
    - metric: synthetic300k_browser_js_heap_mb
      control_median: 45.6
      candidate_median: 58.7
      control_range: [45.2, 45.8]
      candidate_range: [44.7, 63.9]
      change_pct: 28.7
      overlapping: true
    - metric: synthetic300k_browser_interaction_max_ms
      control_median: 48
      candidate_median: 48
      control_range: [40, 48]
      candidate_range: [40, 48]
      change_pct: 0.0
      overlapping: true
    - metric: synthetic300k_backend_index_done_s
      control_median: 15.347
      candidate_median: 19.183
      control_range: [14.858, 16.676]
      candidate_range: [18.857, 19.503]
      change_pct: 25.0
      overlapping: false
    - metric: synthetic300k_backend_first_row_s
      control_median: 0.278
      candidate_median: 0.025
      control_range: [0.278, 1.097]
      candidate_range: [0.022, 0.027]
      change_pct: -91.0
      overlapping: false
    - metric: synthetic300k_backend_peak_rss_mb
      control_median: 283.9
      candidate_median: 291.8
      control_range: [283.8, 284.1]
      candidate_range: [290.5, 291.9]
      change_pct: 2.8
      overlapping: false
    - metric: synthetic300k_backend_tally_overlap_progress_max_ms
      control_median: 92.6
      candidate_median: 98.7
      control_range: [60.6, 162.6]
      candidate_range: [74.8, 125.3]
      change_pct: 6.6
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      Measured on a quiet host: nothing else ran on it, and the 1-minute load average
      stayed below 1.1 for every recorded run, against 10-54 in exp-033. Both wheels
      shared one dependency environment for the browser half and used one environment
      each for compare_builds, all created outside every git work tree and pinned to the
      same standard CPython 3.13.12. Chromium runs with --no-sandbox through a local
      wrapper, because the container is uid 0 with no way to install the setuid sandbox
      helper; both conditions use the identical browser configuration, so pair ratios
      are unaffected.
  verdict:
    decision: rejected
    primary_metric: synthetic300k_browser_first_row_ms
    reason: >-
      On the 300k corpus the candidate crosses the first_row_ms hard gate in three of
      five runs (392, 359 and 364 ms against 350 ms), and run.py compare fails. The walk
      with a browser attached is 1.62-1.78x in all five pairs, the root /api/tree server
      time 2.0-5.3x in all five, LCP 180 -> 416 ms, and two candidate runs record Long
      Tasks where v0.9.1 records none. On the repository-shaped project-10 corpus the
      same candidate passes every hard gate and is 2.5-7x better on first rows, walk
      completion, FCP and LCP. Correctness is clean on both corpora. v0.10.0 stays
      blocked on mb-kicj.
    commit: 03fd7997
---
# exp-034: the quiet-machine v0.10.0 comparison rejects the candidate on the 300k corpus

This is the previous-release comparison for v0.10.0 that
[exp-033](exp-033-v0100-rough-cut-release-sanity-under-load.md) said would be rerun on a
quiet machine after `mb-kicj` was fixed.
The host was quiet: nothing else ran on it, and the 1-minute load average stayed below
1.1 for every recorded run, against 10-54 in exp-033.

**The candidate is rejected.** On the 300k corpus it crosses the `first_row_ms` hard
gate in three of five runs and `run.py compare` fails.
The walk with a browser attached is 1.62-1.78x in every pair, which is the residual
`mb-kicj` names, still present after #122 and larger with a browser attached than
without one.

**On the repository-shaped corpus the same candidate is much better and passes every
hard gate.** That is not in question and is what makes the verdict narrow rather than
general: this release helps the trees people open and hurts a flat, wide,
`.gitignore`-free one.

## The accept rule for this release

The candidate is judged on **back-to-back pairs**, not on one condition’s worst run
against the other’s. Each `compare_builds` iteration runs one control and one candidate
server back to back, and the browser captures alternate in the order C K K C C K K C C
K, so every candidate capture has a control capture beside it.
For each metric the ratio is candidate divided by control, lower is better.

- **Tolerance: 1.3x per pair**, the rule this release was given.
  The loop’s careful tolerance is 1.1x and its fine tolerance 1.05x; this round reports
  those too, because the host was quiet enough to mean them.
- **Rerun:** when exactly one pair exceeds the tolerance, rerun that pair once and judge
  the rerun.
- **Stop:** a metric that exceeds it in two pairs, or again on its rerun, stops the
  release until it is explained.
- **Correctness is strict:** identical ordered rows, tallies differing only where the
  changelog says so, no refused records, complete catalogs, no errors.
- **Hard gate:** `first_row_ms` at 350 ms, applied to every candidate run.

The metrics are browser `first_row_ms`, `walk_elapsed_ms`, root `/api/tree` server time,
`js_heap_mb`, and `interaction_max_ms`, plus backend `first_row`, `index_done`, peak
RSS, spawn-to-serving, and the tally-overlap progress latency.

## Correctness

Correctness passes on both corpora.

- `compare_builds` reports `valid: true` for project-10 and for the 300k corpus, with
  zero ordered-row differences and zero tally differences, and the corpus fingerprint
  unchanged across every run.
- All 20 headed captures were recorded.
  None was refused, every page stayed visible, every index reached `done`, and every
  Quick File catalog is complete (`file_catalog_incomplete` is 0 in all 20).
- The tree region paints once per run on both builds, `reserved_region_shift_px` and
  `frame_missing_px` are identical between conditions, and no run reports a network
  error, a 5xx, a preview error, or a page exception.

## project-10: the repository-shaped corpus

`run.py compare` verdict: **PASS** — evidence admissible, every hard responsiveness
budget passed.

Browser, five back-to-back pairs, median (range):

| Metric | v0.9.1 | candidate | Pair ratios |
| --- | --- | --- | --- |
| `first_row_ms` | 1,238 (1,189-1,392) | 230 (198-317) | 0.26, 0.19, 0.14, 0.21, 0.19 |
| `walk_elapsed_ms` | 39,203 (38,741-40,442) | 15,507 (15,100-16,758) | 0.41, 0.41, 0.39, 0.40, 0.39 |
| `fcp_ms` | 1,140 (1,084-1,260) | 188 (144-316) | 0.29, 0.17, 0.11, 0.16, 0.17 |
| `lcp_ms` | 1,516 (1,432-1,668) | 244 (184-380) | — |
| `last_resource_ms` | 41,330 | 17,160 | — |
| `tree_fetch_srv_ms` | 1 (1-3) | 39 (9-44) | 10.0, 44.0, 3.0, 14.0, 39.0 |
| `js_heap_mb` | 8 (8-9.6) | 24 (21.4-26.6) | 2.77, 2.77, 2.52, 2.50, 3.17 |
| `js_heap_after_gc_mb` | 6.1 (6.1-6.2) | 6.4 (6.4-6.4) | 1.05, 1.05, 1.03, 1.05, 1.03 |
| `interaction_max_ms` | 40 (16-40) | 32 (32-48) | 0.80, 1.00, 2.00, 1.20, 1.33 |
| `long_task_max_ms` | 0 | 0 | — |

Backend, five interleaved pairs:

| Metric | v0.9.1 | candidate | Pair ratios |
| --- | --- | --- | --- |
| `first_row` | 5.806 s (2.911-6.233) | 0.016 s (0.014-0.019) | 0.00 in every pair |
| `index_done` | 39.19 s (35.93-40.80) | 9.315 s (8.74-9.393) | 0.24, 0.24, 0.23, 0.24, 0.24 |
| `peak_rss_mb` | 187.4 (187.2-187.5) | 187.4 (187.2-187.7) | 1.00 in every pair |
| tally-overlap progress | 80.6 ms (50.0-95.7) | 77.6 ms (72.5-158.7) | 1.03, 0.85, 1.45, 1.69, 0.95 |

Three of these need reading rather than quoting.

**Root `/api/tree` server time is 1 ms against 39 ms.** Every pair exceeds the
tolerance, and `load_tree_ms` — the same fetch plus its render — follows at 16-28 ms
against 22-69 ms. The mechanism is the one
[Python inventory cost](../../../docs/project/architecture/arch-python-inventory-cost.md#passes-that-overlap-the-walk)
already states: a provider read through the coordinator is eight loop iterations and a
worker hop, and while the walker holds the GIL in bounded slices each hop waits up to
the 5 ms switch interval.
Eight hops at up to 5 ms is the range observed.
The absolute cost is small and inside every gate — the candidate still reaches first
rows in 198-317 ms against 1,189-1,392 ms — so it is recorded as an explained difference
and tracked as `mb-3s45`, not as a blocker.

**Transient JS heap is 8 MB against 24 MB, and the retained heap is equal.** After a
forced collection both builds sit at about 6 MB, so nothing leaks.
The captures name the cause: `inventory_delivery_batch_items_max` is 256 on v0.9.1 and
4,096 on the candidate.
v0.9.1 had no bound on a delivery batch, so its batch followed the tree — 256 items here
and 11,124 on the 300k corpus.
The candidate always delivers at most 4,096. The transient heap follows the batch, so
this is the cost of a bound that pays for itself on a large tree rather than a
regression to undo (`mb-kccm`).

**The tally-overlap progress latency is not a result at n=5.** Two pairs exceed the
tolerance, which by the rule would stop the release; the reason it does not is that the
metric cannot resolve 1.3x here.
It is a maximum over roughly a hundred samples, and each build’s own runs span more than
the tolerance: v0.9.1 alone ranges 50.0-95.7 ms on this corpus and 60.6-162.6 ms on the
300k one, a 1.9x and 2.7x spread with nothing changed.
The medians are 80.6 against 77.6 ms here and 92.6 against 98.7 ms on 300k, and every
value is far inside the 200 ms budget.
The finding is “no detectable effect”, which is what the accept rule says to write when
ranges overlap. This is the missing noise floor `mb-ot8o` describes, met in practice.

**Spawn-to-serving is bimodal on the control and cannot be read as a pair ratio.** In
the five-pair series v0.9.1 answered at 0.559, 0.575, 0.584, 0.610 and 3.973 s while the
candidate answered at 3.732-3.929 s; in a two-pair series taken minutes later on the
same host and corpus, v0.9.1 answered at 3.708 and 3.816 s, giving ratios of 1.02 and
0.97. The cause is ordering, not work: the candidate’s lifespan awaits `runtime.open`,
which registers the native watcher over 31,481 directories, and Uvicorn binds only after
lifespan startup returns, while v0.9.1 binds first and does the equivalent work
afterwards, so a request that arrives before the loop blocks is answered at once.
Timed end to end in one harness, time-to-first-answer is equal: 3.767 s against 3.746 s.
The candidate’s floor is nonetheless higher, which is worth fixing, and is `mb-lv46`.

## The 300k corpus

`run.py compare` verdict: **FAIL**.

```
Performance gate (exp-034-300k-candidate-03fd7997 is the candidate):
  FAIL
- [budget] first_row_ms is 392; budget is <= 350
- [budget] first_row_ms is 359; budget is <= 350
- [budget] first_row_ms is 364; budget is <= 350
```

Browser, five back-to-back pairs, median (range):

| Metric | v0.9.1 | candidate | Pair ratios |
| --- | --- | --- | --- |
| `first_row_ms` | 293 (282-312) | 359 (312-392) | 1.39, 1.17, 1.06, 1.17, 1.15 |
| `walk_elapsed_ms` | 18,715 (17,777-18,845) | 31,295 (28,852-33,022) | 1.75, 1.78, 1.66, 1.64, 1.62 |
| `tree_fetch_srv_ms` | 6 (6-9) | 22 (12-32) | 3.67, 5.33, 2.75, 3.22, 2.00 |
| `fcp_ms` | 180 (148-220) | 268 (200-276) | 1.86, 1.57, 1.09, 1.49, 1.00 |
| `lcp_ms` | 180 (148-220) | 416 (360-464) | — |
| `last_resource_ms` | 22,281 (21,160-22,476) | 35,139 (33,131-37,122) | — |
| `js_heap_mb` | 45.6 (45.2-45.8) | 58.7 (44.7-63.9) | 1.41, 0.99, 0.98, 1.29, 1.29 |
| `js_heap_after_gc_mb` | 38.3 (38.3-38.5) | 38.9 (38.9-38.9) | 1.01-1.02 |
| `interaction_max_ms` | 48 (40-48) | 48 (40-48) | 1.00, 1.00, 1.20, 0.83, 0.83 |
| `long_task_max_ms` | 0 (0-0) | 0 (0-98) | two candidate runs, 98 ms and 75 ms |

Backend, five interleaved pairs:

| Metric | v0.9.1 | candidate | Pair ratios |
| --- | --- | --- | --- |
| `first_row` | 0.278 s (0.278-1.097) | 0.025 s (0.022-0.027) | 0.02-0.10 |
| `index_done` | 15.35 s (14.86-16.68) | 19.18 s (18.86-19.50) | 1.13, 1.26, 1.24, 1.29, 1.30 |
| `peak_rss_mb` | 283.9 (283.8-284.1) | 291.8 (290.5-291.9) | 1.02-1.03 |
| tally-overlap progress | 92.6 ms (60.6-162.6) | 98.7 ms (74.8-125.3) | 0.61, 1.26, 0.81, 1.89, 1.13 |

**The walk with a browser attached is the finding.** 1.62-1.78x in every pair, on a
quiet machine, where exp-033 measured 1.20-1.91x under load average 10-54 and could not
separate the effect from the host.
Backend-only `index_done` is 1.13-1.30x over the same five pairs, so **attaching a
browser roughly doubles the gap**. Whatever costs the extra time is driven by what the
browser asks for, not by the walker alone.

That points at the passes a browser drives during discovery, and a measurement of those
passes on this corpus, taken separately with a settled index, is the shape of the cost:

| Request | v0.9.1 | candidate | Unrelated request’s worst wait |
| --- | --- | --- | --- |
| `/api/catalog` | 663 ms | 2,575 ms | 475 ms → 883 ms |
| `/api/recent?limit=5000` | 174 ms | 420 ms | 92 ms → 110 ms |
| `/api/tree?depth=0` | 3,794 ms | 4,610 ms | 71 ms → 71 ms |

Priced in isolation at 300,000 rows, the catalog read’s parts are 548 ms building the
contract records (170 ms of it re-validating paths the store admitted at discovery), 196
ms sorting, 113 ms hashing a content identity, and 339 ms encoding a 15.9 MB body — of
which only the filtering loop yields.

The sort line first read here as a free win, on the grounds that the per-row UTF-8
encode produces the same order as sorting the path itself.
The order claim is true — UTF-8 preserves code-point order, and the two agree on every
corpus measured — but removing the encode is not free, and exp-035 corrects the
arithmetic: it is a corpus-dependent trade, not a saving.
v0.9.1 answered the same request from its own retained `(path, ext)` tuples with no
per-row contract object, no validation, no sort-key encode and no content hash.
This is `mb-wpqq`, and the architecture document’s own note that a browser attached
during a walk pays for an entry query, a contract entry, a projection, a decoration and
a wire record per discovered entry is the other half of it.

**The candidate crosses the hard gate.** `first_row_ms` is 392, 359 and 364 ms in three
of five candidate runs against a 350 ms budget.
The gate was calibrated in exp-033 from the worst project-10 candidate first row under
load; it is the release’s stated floor for responsiveness and the candidate does not
clear it here.

**Long Tasks appear where there were none.** Two candidate runs record a 98 ms and a 75
ms Long Task; every v0.9.1 run records zero.
Total blocking time follows, 0 ms against up to 83 ms.
The loop’s own rule is that `long_task_max_ms` must not grow.

## What did not move

Said in the same voice as what did:

- Correctness did not move anywhere: rows, tallies, catalog completeness, repaints.
- `interaction_max_ms` did not move on either corpus once the ranges are read: 16-40 ms
  against 32-48 ms on project-10, and identical 40-48 ms ranges on 300k.
- `reserved_region_shift_px`, `tree_region_repaints`, `frame_missing_px` and
  `collapsed_diff_rows_materialized` are identical between conditions on both corpora.
- Peak RSS is unchanged on project-10 and 2-3% higher on 300k.
- The retained JS heap after a forced collection is equal on both corpora, so the
  transient heap difference is allocation rate, not retention.

## Limits of this round

- One host, one filesystem (ext4), one browser build.
  Absolute numbers do not carry to another machine; the pair ratios are what carries.
- Chromium runs with `--no-sandbox` through a local wrapper, because the container is
  uid 0 and cannot install the setuid sandbox helper.
  Both conditions use the identical browser configuration.
- The 300k corpus is `build_corpus` shape 2: flat, wide, no `.gitignore`. It isolates
  per-entry walker and delivery cost, which is why the regression shows there and not on
  project-10, and it is not a tree anyone has.
- `spawn_to_serving` should not be quoted from this round as a pair ratio; see above.

## What this blocks

v0.10.0 stays blocked on `mb-kicj`. The release-preparation step that renames the
changelog’s `## Unreleased` section is not taken, and no tag is created.
The comparison is rerun on the commit that fixes it, with the same wheels, corpora,
environments and pair rule.

**Superseded on the disposition, not on the measurements.** exp-035 revisits what this
round’s numbers mean for the release and reaches a different answer, by scoping the gate
to the corpus class it was calibrated from rather than by changing any value measured
here. Every number above stands; the verdict above is what this round concluded under a
single gate applied to both corpora, and is kept as that record.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
