---
title: The v0.10.0 rough-cut check rejects the candidate on a 300k walk regression
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-033
  title: The v0.10.0 rough-cut check rejects the candidate on a 300k walk regression
  date: "2026-09-14"
  hypotheses: []
  subject:
    corpus: >-
      repository-shaped project-10 tree-d44cf95e (102,390 walker-visible files, built at
      ec7b23da) and synthetic build_corpus shape 2 tree-b4ec96ce (300,000 files, 1,104
      dirs)
    corpus_files: 102390
    corpus_dirs: 6040
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0
    browser: headed Chrome 152 driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.9.1 wheel built from tag commit 16211ccb
    candidate: exact installed wheel built from 88606b56, the v0.10.0 release candidate
    record: >-
      runs.jsonl labels exp-033-p10-release-v091, exp-033-p10-candidate-88606b56,
      exp-033-300k-release-v091, and exp-033-300k-candidate-88606b56, captured C K K C C K
      with harness 22 in one standard CPython 3.14.7 environment that alternated only the
      wheel; single-pair reruns under exp-033-p10r-* and exp-033-300kr-*; plus three
      compare_builds pairs per corpus and one rerun pair each. Rough-cut 1.3x tolerance on
      back-to-back pair ratios, measured under an unrelated workload (load average 10-54)
  results:
    - metric: project10_backend_spawn_to_serving_s
      control_median: 0.652
      candidate_median: 0.694
      control_range: [0.453, 1.267]
      candidate_range: [0.439, 1.454]
      change_pct: 6.4
      overlapping: true
    - metric: project10_backend_first_row_s
      control_median: 1.08
      candidate_median: 0.012
      control_range: [1.076, 1.196]
      candidate_range: [0.011, 0.012]
      change_pct: -98.9
      overlapping: false
    - metric: project10_backend_index_done_s
      control_median: 15.28
      candidate_median: 5.662
      control_range: [14.218, 17.977]
      candidate_range: [3.702, 6.161]
      change_pct: -62.9
      overlapping: false
    - metric: project10_backend_peak_rss_mb
      control_median: 172.6
      candidate_median: 173.6
      control_range: [172.1, 180.7]
      candidate_range: [173.3, 182.1]
      change_pct: 0.6
      overlapping: true
    - metric: project10_backend_tally_overlap_progress_max_ms
      control_median: 65.5
      candidate_median: 109.8
      control_range: [53.1, 67.0]
      candidate_range: [76.4, 122.1]
      change_pct: 67.6
      overlapping: false
    - metric: project10_browser_first_row_ms
      control_median: 346
      candidate_median: 153
      control_range: [198, 1064]
      candidate_range: [145, 164]
      change_pct: -55.8
      overlapping: false
    - metric: project10_browser_fcp_ms
      control_median: 232
      candidate_median: 112
      control_range: [164, 984]
      candidate_range: [108, 136]
      change_pct: -51.7
      overlapping: false
    - metric: project10_browser_load_tree_ms
      control_median: 71
      candidate_median: 47
      control_range: [68, 71]
      candidate_range: [32, 102]
      change_pct: -33.8
      overlapping: true
    - metric: project10_browser_tree_fetch_srv_ms
      control_median: 1
      candidate_median: 33
      control_range: [1, 3]
      candidate_range: [25, 68]
      change_pct: 3200.0
      overlapping: false
    - metric: project10_browser_walk_elapsed_ms
      control_median: 17241
      candidate_median: 8150
      control_range: [17068, 21433]
      candidate_range: [8099, 10823]
      change_pct: -52.7
      overlapping: false
    - metric: project10_browser_js_heap_mb
      control_median: 21
      candidate_median: 25.8
      control_range: [20.9, 21.8]
      candidate_range: [25.4, 29.2]
      change_pct: 22.9
      overlapping: false
    - metric: project10_browser_js_heap_after_gc_mb
      control_median: 6.3
      candidate_median: 6.4
      control_range: [6.2, 6.5]
      candidate_range: [6.4, 6.4]
      change_pct: 1.6
      overlapping: true
    - metric: project10_browser_interaction_max_ms
      control_median: 24
      candidate_median: 24
      control_range: [0, 352]
      candidate_range: [0, 24]
      change_pct: 0.0
      overlapping: true
    - metric: project10_browser_inventory_delivery_batch_items_max
      control_median: 1463
      candidate_median: 4096
      control_range: [1275, 2939]
      candidate_range: [4096, 4096]
      change_pct: 180.0
      overlapping: false
    - metric: project10_browser_long_tasks
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: project10_browser_file_catalog_incomplete
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: synthetic300k_backend_spawn_to_serving_s
      control_median: 0.767
      candidate_median: 0.748
      control_range: [0.595, 0.812]
      candidate_range: [0.732, 0.78]
      change_pct: -2.5
      overlapping: true
    - metric: synthetic300k_backend_first_row_s
      control_median: 0.788
      candidate_median: 0.016
      control_range: [0.28, 0.799]
      candidate_range: [0.016, 0.016]
      change_pct: -98.0
      overlapping: false
    - metric: synthetic300k_backend_index_done_s
      control_median: 12.302
      candidate_median: 14.518
      control_range: [11.585, 12.857]
      candidate_range: [14.174, 18.38]
      change_pct: 18.0
      overlapping: false
    - metric: synthetic300k_backend_peak_rss_mb
      control_median: 307.0
      candidate_median: 318.6
      control_range: [306.4, 308.0]
      candidate_range: [317.0, 320.6]
      change_pct: 3.8
      overlapping: false
    - metric: synthetic300k_backend_tally_overlap_progress_max_ms
      control_median: 82.2
      candidate_median: 243.0
      control_range: [69.8, 99.5]
      candidate_range: [118.4, 254.3]
      change_pct: 195.6
      overlapping: false
    - metric: synthetic300k_browser_first_row_ms
      control_median: 173
      candidate_median: 185
      control_range: [122, 256]
      candidate_range: [169, 226]
      change_pct: 6.9
      overlapping: true
    - metric: synthetic300k_browser_fcp_ms
      control_median: 136
      candidate_median: 152
      control_range: [100, 160]
      candidate_range: [116, 180]
      change_pct: 11.8
      overlapping: true
    - metric: synthetic300k_browser_load_tree_ms
      control_median: 19
      candidate_median: 35
      control_range: [13, 21]
      candidate_range: [34, 49]
      change_pct: 84.2
      overlapping: false
    - metric: synthetic300k_browser_tree_fetch_srv_ms
      control_median: 5
      candidate_median: 27
      control_range: [4, 9]
      candidate_range: [23, 27]
      change_pct: 440.0
      overlapping: false
    - metric: synthetic300k_browser_walk_elapsed_ms
      control_median: 14025
      candidate_median: 21722
      control_range: [11442, 15422]
      candidate_range: [19525, 21898]
      change_pct: 54.9
      overlapping: false
    - metric: synthetic300k_browser_js_heap_mb
      control_median: 44.9
      candidate_median: 59.7
      control_range: [44.1, 44.9]
      candidate_range: [42.9, 59.7]
      change_pct: 33.0
      overlapping: true
    - metric: synthetic300k_browser_js_heap_after_gc_mb
      control_median: 38.5
      candidate_median: 38.9
      control_range: [38.3, 38.5]
      candidate_range: [38.9, 38.9]
      change_pct: 1.0
      overlapping: false
    - metric: synthetic300k_browser_interaction_max_ms
      control_median: 24
      candidate_median: 24
      control_range: [24, 24]
      candidate_range: [16, 32]
      change_pct: 0.0
      overlapping: true
    - metric: synthetic300k_browser_inventory_delivery_batch_items_max
      control_median: 56238
      candidate_median: 4096
      control_range: [53766, 60700]
      candidate_range: [4096, 4096]
      change_pct: -92.7
      overlapping: false
    - metric: synthetic300k_browser_long_tasks
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: synthetic300k_browser_file_catalog_incomplete
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      Measured while another session's unrelated jobs held the 1-minute load average at
      22-34 during the project-10 series and backend, 27-54 during the 300k series and
      backend, and 10-23 during the reruns, so this is a rough-cut check and not a
      performance claim. Both wheels shared one dependency environment for the browser
      half and used one environment each for compare_builds. The first_row_ms hard gate
      was added after these runs were recorded, so compare applied it to them while
      record did not.
  verdict:
    decision: rejected
    primary_metric: synthetic300k_browser_walk_elapsed_ms
    reason: >-
      The rough-cut 1.3x back-to-back gate found a repeatable 300k walk and index
      regression (mb-kicj): walk pair ratios 1.20-1.91 and index_done 1.13-1.49, repeating
      at load 10. It also found a candidate-only tally-overlap progress-latency budget
      miss, 213-254 ms against 200 ms in three of four 300k backend runs, and a 300k
      first_row_ms and transient js_heap_mb excess. Correctness passes on both corpora,
      with identical ordered rows and tallies, and on project-10 the candidate is more
      than twice as fast to first rows, walk completion, and backend index completion.
      The project-10 tree_fetch_srv_ms and interaction_max_ms excesses are explained and
      are not grounds for rejection. v0.10.0 is blocked on mb-kicj, and this comparison
      will be rerun on the fixed commit.
    commit: 88606b56
---
# exp-033: the v0.10.0 rough-cut check rejects the candidate on a 300k walk regression

This is the previous-release comparison for v0.10.0, run on the release candidate
`88606b56` against the exact v0.9.1 wheel.
It is a **rough cut**, not a performance measurement.
Another session’s unrelated jobs held the host’s 1-minute load average between 10 and 54
throughout, and the release could not wait for a quiet machine.

**The candidate is rejected.** The 300k corpus shows a repeatable walk and index
regression, tracked as `mb-kicj`, a candidate-only progress-latency budget miss during
tallies, and a first-row and transient heap excess.
v0.10.0 is blocked on `mb-kicj`, and this comparison will be rerun on the fixed commit.
The project-10 result below, where the candidate is much faster, is not in question.

## The accept rule for this release

The candidate is judged on **back-to-back pairs**, not on one condition’s worst run
against the other’s. The browser runs were captured in the order C K K C C K, giving the
pairs (C1, K1), (K2, C2), and (C3, K3); each `compare_builds` iteration runs one control
and one candidate server back to back.
For each key metric the ratio is candidate divided by control, lower is better.

- **Tolerance: 1.3x**, the rough-cut tolerance for a sanity check on a loaded machine.
  A careful measurement on a quiet machine uses 1.1x, or 1.05x for a fine claim; see
  [the loop README](../README.md#comparing-a-candidate-with-the-previous-release).
- **Rerun:** when exactly one pair exceeds 1.3x on a metric, rerun that pair back to
  back once and judge the rerun.
- **Stop:** a metric that exceeds 1.3x in two or more pairs, or again on its rerun,
  stops the release until it is explained and accepted or fixed.
- **Correctness is strict:** identical ordered rows, tally differences only where the
  changelog documents them, no refused records, complete catalogs, and no errors.
- **Hard gates under load:** a candidate miss is load only when the adjacent control run
  misses the same gate by a comparable margin.

The key metrics are browser `first_row_ms`, `walk_elapsed_ms`, root `/api/tree` server
time (`tree_fetch_srv_ms`), `js_heap_mb`, and `interaction_max_ms`, plus backend
`first_row`, `index_done`, peak RSS, and spawn-to-serving.

## Correctness

Correctness passes on both corpora.

- `compare_builds` finds zero ordered-row and zero tally differences on project-10 and
  on the 300k corpus, in the main runs and in both reruns, and the corpus fingerprint is
  unchanged.
- All 20 headed captures (six per corpus plus four reruns per corpus) were recorded.
  None was refused, every page stayed visible, every index reached `done`, and every
  Quick File catalog is complete.
- No run reports a Long Task, network error, 5xx response, preview error, or page
  exception. The tree region paints once in every run.

## project-10: the repository-shaped corpus

Load average (1 minute) around each pair: pair 1 29.8-31.8, pair 2 32.0-32.6, pair 3
31.3-33.5, the pair-2 rerun 16.9-23.3, the pair-3 rerun 16.3-19.5.

| Metric (control / candidate = ratio) | Pair 1 | Pair 2 | Pair 3 | Pair 2 rerun | Pair 3 rerun |
| --- | --- | --- | --- | --- | --- |
| `first_row_ms` | 1064 / 145 = 0.14 | 346 / 164 = 0.47 | 198 / 153 = 0.77 | 368 / 269 = 0.73 | 490 / 144 = 0.29 |
| `walk_elapsed_ms` | 21433 / 10823 = 0.50 | 17241 / 8099 = 0.47 | 17068 / 8150 = 0.48 | 20689 / 9399 = 0.45 | 22302 / 11987 = 0.54 |
| `tree_fetch_srv_ms` | 3 / 33 = 11.0 | 1 / 25 = 25.0 | 1 / 68 = 68.0 | 1 / 12 = 12.0 | 1 / 39 = 39.0 |
| `js_heap_mb` | 21.8 / 25.8 = 1.18 | 21.0 / 25.4 = 1.21 | 20.9 / 29.2 = **1.40** | 8.6 / 22.7 = 2.64 | 20.8 / 25.9 = 1.25 |
| `js_heap_after_gc_mb` | 6.5 / 6.4 = 0.98 | 6.3 / 6.4 = 1.02 | 6.2 / 6.4 = 1.03 | 6.3 / 6.4 = 1.02 | 6.4 / 6.4 = 1.00 |
| `interaction_max_ms` | 352 / 0 = 0.00 | 0 / 24 | 24 / 24 = 1.00 | 0 / 32 | 0 / 0 |

| Backend (control / candidate = ratio) | Pair 1 | Pair 2 | Pair 3 | Pair 3 rerun |
| --- | --- | --- | --- | --- |
| Load average | 25.3 / 24.0 | 22.2 / 22.1 | 24.6 / 24.7 | 15.9 / 17.0 |
| `spawn_to_serving` s | 1.267 / 1.454 = 1.15 | 0.652 / 0.439 = 0.67 | 0.453 / 0.694 = **1.53** | 0.621 / 0.768 = 1.24 |
| `first_row` s | 1.076 / 0.011 = 0.01 | 1.080 / 0.012 = 0.01 | 1.196 / 0.012 = 0.01 | 1.098 / 0.014 = 0.01 |
| `index_done` s | 15.28 / 6.16 = 0.40 | 14.22 / 5.66 = 0.40 | 17.98 / 3.70 = 0.21 | 18.29 / 7.58 = 0.41 |
| `peak_rss_mb` | 180.7 / 182.1 = 1.01 | 172.1 / 173.3 = 1.01 | 172.6 / 173.6 = 1.01 | 172.3 / 173.7 = 1.01 |
| Tally-overlap progress max ms (not a key metric) | 65.5 / 122.1 = 1.86 | 67.0 / 109.8 = 1.64 | 53.1 / 76.4 = 1.44 | 73.4 / 97.8 = 1.33 |

On this corpus the candidate is the release its changelog describes.
Browser first rows arrive at 144-269 ms against 198-1,064 ms; the backend returns its
first nonempty root rows in 11-14 ms against about 1.1 s; the walk with a browser
attached takes half as long; and backend index completion is 2.4-4.9 times faster.
That is the removed whole-repository `.gitignore` pre-walk.
Spawn-to-serving and the single `js_heap_mb` exceedance resolve within 1.3x on their
reruns.

Two metrics exceed the tolerance, and neither is a regression:

- **Root `/api/tree` server time** exceeds in every pair, at 12-68 ms against 1-3 ms.
  The time a reader waits did not grow: `tree_fetch_wait_ms`, which includes time queued
  before the server’s timing middleware starts, is 13-74 ms for the candidate and 53-116
  ms for v0.9.1, and settled re-probes take 1 ms against 2-3 ms.
  v0.9.1 answered the tree synchronously on the event loop, so its time waiting behind
  the walker fell outside `srv`. The candidate’s provider read runs in a worker thread
  (`asyncio.to_thread(self._read_sync, request)`), so the same wait now falls inside it.
  exp-032 recorded the same shift, from 3 to 14 ms.
- **`interaction_max_ms`** exceeds in pair 2 and again on its rerun, but the control
  side of both is 0, meaning no interaction crossed Event Timing’s reporting threshold.
  The candidate’s worst is 24-32 ms against a 200 ms hard gate, while v0.9.1 reached 352
  ms in pair 1.

The pair-2 rerun also shows `js_heap_mb` at 2.64 because that control’s natural heap
sample, 8.6 MB, is less than half of the other four control runs’ 20.8-21.8 MB. Retained
heap after garbage collection is equal in every pair.

## The 300k synthetic corpus

Load average (1 minute) around each pair: pair 1 27.1-34.6, pair 2 33.6-40.4, pair 3
40.4-50.5, the pair-1 rerun 13.3-15.4, the pair-3 rerun 10.7-14.3.

| Metric (control / candidate = ratio) | Pair 1 | Pair 2 | Pair 3 | Pair 1 rerun | Pair 3 rerun |
| --- | --- | --- | --- | --- | --- |
| `first_row_ms` | 256 / 226 = 0.88 | 173 / 169 = 0.98 | 122 / 185 = **1.52** | 155 / 209 = 1.35 | 156 / 303 = **1.94** |
| `walk_elapsed_ms` | 14025 / 19525 = **1.39** | 15422 / 21722 = **1.41** | 11442 / 21898 = **1.91** | 14750 / 26164 = 1.77 | 16160 / 19333 = 1.20 |
| `tree_fetch_srv_ms` | 4 / 23 = 5.75 | 5 / 27 = 5.40 | 9 / 27 = 3.00 | 4 / 23 = 5.75 | 8 / 25 = 3.12 |
| `load_tree_ms` (reader-visible) | 19 / 35 = 1.84 | 13 / 34 = 2.62 | 21 / 49 = 2.33 | - | - |
| `js_heap_mb` | 44.9 / 42.9 = 0.96 | 44.9 / 59.7 = **1.33** | 44.1 / 59.7 = **1.35** | 44.7 / 42.4 = 0.95 | 44.5 / 42.2 = 0.95 |
| `js_heap_after_gc_mb` | 38.5 / 38.9 = 1.01 | 38.3 / 38.9 = 1.02 | 38.5 / 38.9 = 1.01 | 38.5 / 38.9 = 1.01 | 38.5 / 38.9 = 1.01 |
| `interaction_max_ms` | 24 / 32 = **1.33** | 24 / 24 = 1.00 | 24 / 16 = 0.67 | 32 / 24 = 0.75 | 16 / 24 = 1.50 |

| Backend (control / candidate = ratio) | Pair 1 | Pair 2 | Pair 3 | Pair 3 rerun |
| --- | --- | --- | --- | --- |
| Load average | 51.6 / 53.5 | 50.8 / 45.4 | 39.6 / 37.1 | 10.2 / 9.8 |
| `spawn_to_serving` s | 0.595 / 0.748 = 1.26 | 0.812 / 0.780 = 0.96 | 0.767 / 0.732 = 0.95 | 0.600 / 0.780 = 1.30 |
| `first_row` s | 0.280 / 0.016 = 0.06 | 0.799 / 0.016 = 0.02 | 0.788 / 0.016 = 0.02 | 0.552 / 0.016 = 0.03 |
| `index_done` s | 11.59 / 14.17 = 1.22 | 12.86 / 14.52 = 1.13 | 12.30 / 18.38 = **1.49** | 10.04 / 14.01 = **1.40** |
| `peak_rss_mb` | 308.0 / 318.6 = 1.03 | 306.4 / 317.0 = 1.03 | 307.0 / 320.6 = 1.04 | 305.0 / 319.3 = 1.05 |
| Tally-overlap progress max ms (200 ms budget) | 99.5 / **243.0** | 82.2 / **254.3** | 69.8 / 118.4 | 105.1 / **213.4** |

Catalog delivery is bounded as exp-032 found: in the main series, batches of 4,096 items
against v0.9.1’s 53,766-60,700, and a worst delivery callback of 7 ms against 18-19 ms.
Backend first rows arrive in 16 ms against 0.28-0.80 s.

Four findings reject the candidate:

- **Walk completion** is slower with a browser attached, at 19.3-26.2 s against
  11.4-16.2 s, and without one: `index_done` is 1.13-1.49 times the control and exceeds
  again at load 10. This is a flat, wide synthetic tree with no `.gitignore`, so the
  candidate gains nothing from the removed pre-walk and pays its per-entry costs.
  It matches exp-032’s unresolved walk result and the residual in `mb-kicj`.
- **Tally-overlap progress latency** crosses `compare_builds`’ 200 ms budget for the
  candidate in three of four runs, at 213-254 ms, while v0.9.1 stays at 70-105 ms under
  the same load. The backend report is therefore `valid: false` despite identical rows
  and tallies. This is a candidate-only miss.
- **First rows** exceed in pair 3 (122 to 185 ms) and again on its rerun at load 11-14
  (156 to 303 ms). Every candidate first row is still inside the 350 ms hard gate.
- **`js_heap_mb`** exceeds in pairs 2 and 3, at 59.7 MB against about 45 MB. Retained
  heap after collection differs by 0.4-0.6 MB, so this is transient allocation, as in
  exp-032, and both reruns show 0.95.

Two more results need re-measuring on the fixed commit:

- **Root `/api/tree`** server time exceeds in every pair, for the provider-thread reason
  given for project-10. Here `load_tree_ms` rises with it, from 13-21 ms to 34-49 ms, so
  about 20 ms of that wait reaches the reader on this corpus.
- **`interaction_max_ms`** resolves on its pair-1 rerun (0.75). The pair-3 rerun shows
  1.50, but at 16 to 24 ms.

## Hard gates under load

Every candidate browser run passes every hard gate, including the new `first_row_ms`
gate. The v0.9.1 misses are not shared by the candidate:

- `inventory_delivery_attribution_missing` is 1 in every v0.9.1 run, the known release
  gap from exp-032.
- `interaction_max_ms` reached 352 ms and `startup_style_server_ms_max` 368 ms in
  project-10 pair 1 at load 30, and the stylesheet server time was also 90-96 ms in both
  project-10 reruns.

The only candidate-only hard miss is the backend tally-overlap progress budget on the
300k corpus.

## The first-row hard gate

`first_row_ms` is now a hard gate at **350 ms** in `performance-budgets.toml`. It is a
rough-cut value: 1.3 times the worst candidate first row on project-10 in this round,
269 ms, rounded up. It exists to reject the class of regression v0.1.0 through v0.9.1
shipped, where the `.gitignore` pre-walk held a repository’s first rows for 9-34 s, and
should be recalibrated from a quiet-machine measurement at the careful 1.1x tolerance.
An unrecorded dry run of an earlier main commit on this host, at load 19, took 468 ms,
so a heavily loaded host can still cross this gate spuriously.

## What this does not establish

The ratios above are rough-cut evidence from one loaded host.
They can show a regression of the pre-walk’s size, and they show that the 300k discovery
path is slower in the candidate under contention, but they cannot size either effect
precisely. The quiet-machine revalidation `mb-afdb` asked for has still not been run.

The next round reruns this comparison on the commit that fixes `mb-kicj`, against the
same v0.9.1 wheel, corpora, and environments, and applies the same pair rule.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
