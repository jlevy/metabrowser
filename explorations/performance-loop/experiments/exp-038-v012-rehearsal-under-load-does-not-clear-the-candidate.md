---
title: A release rehearsal under load finds the v0.12 candidate equivalent to v0.11.0 and does not clear it
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-038
  title: A release rehearsal under load finds the v0.12 candidate equivalent to v0.11.0 and does not clear it
  date: "2026-10-01"
  hypotheses: []
  subject:
    corpus: >-
      repository-shaped project-10 tree-43a9225a, built fresh on this host at c16912f8 by
      build_project_corpus: 236,752 files in 30,201 directories on disk, of which 113,030
      files in 6,560 directories are visible to the walker. It is a new tree, so nothing
      here compares with an earlier round's numbers
    corpus_files: 113030
    corpus_dirs: 6560
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7
    browser: headed Chrome 152 driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: exact installed v0.11.0 wheel built from tag commit 6c278f3f
    candidate: >-
      exact installed wheel built from c16912f8, the head of the v0.12 stack when the
      rehearsal ran; it is a rehearsal candidate and not the commit to be tagged
    record: >-
      runs.jsonl labels exp-038-pyc-release-v0.11.0 and exp-038-pyc-candidate-c16912f8,
      five headed captures per condition in the order C K K C C K K C C K, harness 22,
      one environment alternating only the Metabrowser wheel, with every module compiled
      to bytecode after each swap; one rerun pair under exp-038-pycr5-*; a second
      five-pair series under exp-038-pyc2-*; and a first series under exp-038-release-v0.11.0
      and exp-038-candidate-c16912f8 taken before the environments had bytecode. Two
      compare_builds runs of five pairs with bytecode and two without, twelve
      startup_pairs rounds in each regime, and five walk pairs. The 1.3x rough-cut rule
      on back-to-back pairs, under a 1-minute load average of 11 to 109 for the browser
      captures
  results:
    - metric: project10_browser_first_row_ms
      control_median: 224
      candidate_median: 224
      control_range: [183, 1507]
      candidate_range: [163, 783]
      change_pct: 0.0
      overlapping: true
    - metric: project10_browser_fcp_ms
      control_median: 164
      candidate_median: 168
      control_range: [136, 736]
      candidate_range: [104, 500]
      change_pct: 2.4
      overlapping: true
    - metric: project10_browser_load_tree_ms
      control_median: 55
      candidate_median: 56
      control_range: [8, 305]
      candidate_range: [33, 132]
      change_pct: 1.8
      overlapping: true
    - metric: project10_browser_tree_fetch_srv_ms
      control_median: 44
      candidate_median: 47
      control_range: [13, 252]
      candidate_range: [27, 58]
      change_pct: 6.8
      overlapping: true
    - metric: project10_browser_walk_elapsed_ms
      control_median: 20955
      candidate_median: 17497
      control_range: [11951, 44151]
      candidate_range: [12640, 35799]
      change_pct: -16.5
      overlapping: true
    - metric: project10_browser_startup_style_server_ms_max
      control_median: 44.7
      candidate_median: 44.2
      control_range: [28.3, 379.1]
      candidate_range: [11.9, 122.5]
      change_pct: -1.1
      overlapping: true
    - metric: project10_browser_interaction_max_ms
      control_median: 24
      candidate_median: 16
      control_range: [0, 32]
      candidate_range: [0, 24]
      change_pct: -33.3
      overlapping: true
    - metric: project10_browser_long_task_max_ms
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: project10_browser_js_heap_mb
      control_median: 15.4
      candidate_median: 11
      control_range: [9.9, 36.2]
      candidate_range: [9.9, 19.6]
      change_pct: -28.6
      overlapping: true
    - metric: project10_browser_js_heap_after_gc_mb
      control_median: 8.1
      candidate_median: 8.1
      control_range: [8, 8.2]
      candidate_range: [8.1, 8.1]
      change_pct: 0.0
      overlapping: true
    - metric: project10_browser_startup_script_transfer_kb
      control_median: 171
      candidate_median: 173
      control_range: [171, 171]
      candidate_range: [173, 173]
      change_pct: 1.2
      overlapping: false
    - metric: project10_browser_script_transfer_kb
      control_median: 351
      candidate_median: 371
      control_range: [351, 351]
      candidate_range: [371, 371]
      change_pct: 5.7
      overlapping: false
    - metric: project10_browser_dom_nodes
      control_median: 1062
      candidate_median: 1066
      control_range: [1062, 1062]
      candidate_range: [1066, 1066]
      change_pct: 0.4
      overlapping: false
    - metric: project10_browser_frame_missing_px
      control_median: 220
      candidate_median: 670
      control_range: [220, 220]
      candidate_range: [670, 670]
      change_pct: 204.5
      overlapping: false
    - metric: project10_backend_first_row_s
      control_median: 0.035
      candidate_median: 0.103
      control_range: [0.012, 0.054]
      candidate_range: [0.012, 0.147]
      change_pct: 194.3
      overlapping: true
    - metric: project10_backend_index_done_s
      control_median: 13.953
      candidate_median: 13.215
      control_range: [4.504, 14.865]
      candidate_range: [4.75, 17.712]
      change_pct: -5.3
      overlapping: true
    - metric: project10_backend_peak_rss_mb
      control_median: 180.6
      candidate_median: 182.7
      control_range: [177, 182.6]
      candidate_range: [180, 185.7]
      change_pct: 1.2
      overlapping: true
    - metric: project10_backend_tally_overlap_progress_max_ms
      control_median: 75
      candidate_median: 62.7
      control_range: [56.3, 215.3]
      candidate_range: [40.9, 174]
      change_pct: -16.4
      overlapping: true
    - metric: cli_show_instr_millions
      control_median: 2425.1
      candidate_median: 2529.9
      control_range: [2362.9, 2521.4]
      candidate_range: [2407.4, 2597.7]
      change_pct: 4.3
      overlapping: true
    - metric: cli_doctor_instr_millions
      control_median: 1957
      candidate_median: 3491.8
      control_range: [1947.7, 2051.5]
      candidate_range: [3462.3, 3603.9]
      change_pct: 78.4
      overlapping: false
    - metric: cli_walk_instr_millions
      control_median: 50663.9
      candidate_median: 50081.8
      control_range: [49713.8, 54447.4]
      candidate_range: [49950.2, 51853.7]
      change_pct: -1.1
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      Unrelated jobs from other sessions held the host's 1-minute load average between 11
      and 109 during the browser captures, 17 and 31 during the two backend comparisons
      taken with bytecode, and 48 and 97 during the walk pairs. No window stayed quiet
      for a whole series. The first browser series, the first two backend comparisons
      and the first start-up series ran in environments with no compiled bytecode,
      because the session's shell sets PYTHONDONTWRITEBYTECODE; both builds were in the
      same state, and those runs are kept and labelled, and are not the comparison.
  verdict:
    decision: unresolved
    primary_metric: project10_browser_first_row_ms
    reason: >-
      Not cleared, and not rejected. Correctness holds: four backend comparisons find
      zero ordered-row and zero tally differences, and all 32 headed captures were
      recorded, visible, complete, and free of Long Tasks, errors and exceptions. The
      release rule that every candidate run pass the hard gates is not met: the
      candidate missed first_row_ms in 5 of 11 captures taken with bytecode, each at a
      load average above 30, and v0.11.0 missed it in 6 of its 11, two of them below
      30. A gate the released build fails as often on the same host measures the host.
      Pair ratios scatter both ways, 0.25 to 3.50 on first rows, so the 1.3x rule can
      neither accept nor reject. What does not depend on load agrees between the
      builds: instructions retired for a walk 0.99x, to start 1.02x to 1.04x, startup
      scripts 173 KB against the 175 KB gate, retained heap equal. Two results need a
      decision or a fix before a release: --doctor does 1.78x the work by design and
      exceeds the tolerance in every pair, and frame_missing_px reads 670 against 220
      because the probe's stand-in no longer fits the page, not because the frame
      changed. The headed series is owed on a quiet machine.
    commit: c16912f8
---
# exp-038: a release rehearsal under load finds the v0.12 candidate equivalent to v0.11.0 and does not clear it

This is the previous-release comparison of the
[release checklist](../../../docs/publishing.md#release-checklist), run early as a
rehearsal on `c16912f8`, the head of the v0.12 stack on October 1, against the exact
v0.11.0 wheel.
It is a **rough cut**: other sessions’ jobs kept the host busy throughout,
and no series ran under a steady load.

**The candidate is not cleared.** It is not rejected either.
The builds return the same answers and do the same amount of work where work can be
counted.
The wall-clock half could not be judged: both builds, the released one included,
missed the first-row hard gate in about half their captures.
The comparison has to be repeated on a quiet machine, on the commit that will be tagged.

## What was run

Both wheels were built the way `make build` builds a release, with
`uv build --no-build-isolation` from a synced checkout: the control from the `v0.11.0`
tag (`6c278f3f`) in a detached worktree, the candidate from `c16912f8` with a clean
tree. The candidate wheel is byte-identical to the one `make verify` built from the same
commit.

Three environments were created outside every work tree, from the candidate’s locked
dependency versions: one shared by both conditions of the browser half, with only the
Metabrowser wheel swapped, and one per build for `compare_builds`. `uv pip check` passed
with either wheel in the shared environment, so the two builds run on the same
dependencies even though the candidate adds `softschema` and raises
`frontmatter-format`. Each `metab --version` was matched against its wheel before a
measurement.

The corpus is `project-10`, built on this host for this round, because the host had none
of that shape. `compare_builds` fingerprinted it before and after each of its runs, and
`record` after every capture; it did not change.

### Bytecode

The session’s shell sets `PYTHONDONTWRITEBYTECODE`, so an environment created in it has
no `.pyc` files, and every start compiles every module it imports.
`--version` retires 5.5 billion instructions in that state and 1.9 billion with bytecode
present, which is what a user’s installation has after its first run.

The first browser series, the first two backend comparisons and the first start-up
series were taken before this was noticed.
Both builds were in the same state, so those runs compare like with like, in a regime no
user is in. They are kept under their own labels and named “without bytecode” below.

Everything else ran after `python -m compileall` over each environment’s
`site-packages`, repeated for the Metabrowser package after every wheel swap in the
shared environment, with a check before each `serve` that every Metabrowser module had
its bytecode. The measured processes inherit the variable, which stops Python writing
bytecode and does not stop it reading it.

### The series

| Series | Labels | Captures | Load average, 1 minute |
| --- | --- | --- | --- |
| Without bytecode | `exp-038-release-v0.11.0`, `exp-038-candidate-c16912f8` | 5 pairs | 58 falling to 11 |
| With bytecode | `exp-038-pyc-*` | 5 pairs | 21 to 41, then 92 in pair 5 |
| Rerun of pair 5 | `exp-038-pycr5-*` | 1 pair | 18 to 20 |
| With bytecode, second | `exp-038-pyc2-*` | 5 pairs | 13 to 21 in pairs 1 and 2, 22 to 109 after |

Each series opened with the unrecorded warm-up cycle and alternated the order within
pairs: C K, K C, C K, K C, C K. Every capture was a fresh visible Chrome profile making
one page load. The front matter’s browser results are the first series with bytecode.

## The accept rule

The rule is exp-033’s, from
[the loop README](../README.md#comparing-a-candidate-with-the-previous-release):

- candidate divided by control for each back-to-back pair, tolerance **1.3x**;
- a metric over the tolerance in exactly one pair is rerun once, and one over it in two
  pairs or on the rerun stops the release until it is explained;
- every candidate run passes the hard gates, and a miss counts as load only when the
  adjacent control run misses the same gate by a comparable margin;
- correctness is strict.

## Correctness

Correctness passes.

- `compare_builds` ran four times, five interleaved pairs each: zero ordered-row
  differences and zero tally differences in every run, no errors, and the corpus
  fingerprint unchanged.
  Three reports are `valid: true`. The first, without bytecode at a load average of
  130–187, is `valid: false` for one reason: the candidate’s tally-overlap progress
  latency reached 211.4 ms in one run against the comparator’s 200 ms budget.
  The control reached 242.1 ms in the same report, and 215.3, 206.6 and 263.7 ms in the
  other three, where it is not gated.
  That is the host, not a response difference.
- `metab ROOT --walk --format json` wrote 46,721,591 bytes from each build in five
  pairs.
- All 32 headed captures were recorded.
  None was refused, every page stayed visible, every index reached `done`, every Quick
  File catalog is complete, and trusted input covered 93.8–98.7% of every loading
  window.
- No capture of either build reports a Long Task, a blocked animation frame, a network
  error, a 4xx or 5xx response, an aborted fetch, a preview error or a page exception.
  The worst interaction in any capture took 40 ms against the 200 ms gate.
  The tree region paints once in every capture.

## Hard gates

Every responsiveness and correctness gate passed in all 32 captures.
Two wall-clock gates did not: `first_row_ms` (350 ms) and `startup_style_server_ms_max`
(75 ms).

`first_row_ms` per capture, as control / candidate, with the load average around the
pair. Bold is a miss.

| Series | Pair 1 | Pair 2 | Pair 3 | Pair 4 | Pair 5 |
| --- | --- | --- | --- | --- | --- |
| Without bytecode | **1,634** / **737** | **358** / 323 | 218 / 146 | 140 / 115 | 148 / 185 |
| Load | 58–31 | 29–21 | 20–16 | 17–14 | 14–11 |
| With bytecode | **1,507** / **377** | 190 / 224 | 183 / 187 | **588** / 163 | 224 / **783** |
| Load | 22–41 | 34–29 | 27–34 | 25–21 | 21–92 |
| With bytecode, second | 171 / 128 | 163 / 141 | **565** / **710** | **702** / **964** | **1,222** / **495** |
| Load | 13–16 | 13–21 | 22–49 | 47–62 | 59–109 |

The rerun of pair 5 read **486** / 302 at a load average of 18–20.

`startup_style_server_ms_max` missed in a subset of the same captures: the control at
459.5, 379.1, 201.4, 213.6 and 300.1 ms, the candidate at 94.1, 122.5, 258.2 and 77.9
ms.

| Captures with a hard-gate miss | v0.11.0 | Candidate |
| --- | --- | --- |
| Without bytecode | 2 of 5 | 1 of 5 |
| With bytecode | 2 of 5 | 2 of 5 |
| Rerun of pair 5 | 1 of 1 | 0 of 1 |
| With bytecode, second | 3 of 5 | 3 of 5 |

Every candidate miss came with a load average above 30 before or after the capture.
In the eight candidate captures whose load average stayed below 30, the worst first row
took 323 ms without bytecode and 302 ms with it.
The control missed three times in its eight: 358, 588 and 486 ms.

By the pair rule, five of the candidate’s six misses are load: the adjacent control
missed the same gate, by more in three of them.
The sixth is pair 5 with bytecode, where the control passed at 224 ms and the candidate
took 783 ms. The load average was 21 when the control’s capture began and 92 for the
candidate’s, and the rerun of that pair at a steady load gave 486 / 302.

`run.py compare` therefore reports FAIL for the candidate in all three five-pair series.
exp-033 recorded that a load average of 19 took an unrecorded run of this gate to 468
ms. This round shows the same of the released build, which fails the gate here in half
its captures. The gate did not measure the candidate.

## Pair ratios

Key metrics, control / candidate = ratio, for the series with bytecode.
Bold is above 1.3x.

| Metric | Pair 1 | Pair 2 | Pair 3 | Pair 4 | Pair 5 | Pair 5 rerun |
| --- | --- | --- | --- | --- | --- | --- |
| `first_row_ms` | 1,507 / 377 = 0.25 | 190 / 224 = 1.18 | 183 / 187 = 1.02 | 588 / 163 = 0.28 | 224 / 783 = **3.50** | 486 / 302 = 0.62 |
| `walk_elapsed_ms` | 44,151 / 20,980 = 0.48 | 16,103 / 13,002 = 0.81 | 11,951 / 12,640 = 1.06 | 20,955 / 17,497 = 0.83 | 25,657 / 35,799 = **1.40** | 17,642 / 19,738 = 1.12 |
| `tree_fetch_srv_ms` | 252 / 47 = 0.19 | 72 / 29 = 0.40 | 13 / 58 = **4.46** | 28 / 27 = 0.96 | 44 / 52 = 1.18 | 37 / 73 = **1.97** |
| `load_tree_ms` | 305 / 56 = 0.18 | 82 / 33 = 0.40 | 19 / 65 = **3.42** | 8 / 34 = **4.25** | 55 / 132 = **2.40** | 46 / 81 = **1.76** |
| `startup_style_server_ms_max` | 379.1 / 122.5 = 0.32 | 44.7 / 17.2 = 0.38 | 28.3 / 44.2 = **1.56** | 201.4 / 11.9 = 0.06 | 42.8 / 70.4 = **1.64** | 49.5 / 46.6 = 0.94 |
| `js_heap_mb` | 9.9 / 15.3 = **1.55** | 15.4 / 10.8 = 0.70 | 36.2 / 9.9 = 0.27 | 17.3 / 19.6 = 1.13 | 12.6 / 11.0 = 0.87 | 16.1 / 11.1 = 0.69 |
| `js_heap_after_gc_mb` | 8.1 / 8.1 = 1.00 | 8.2 / 8.1 = 0.99 | 8.0 / 8.1 = 1.01 | 8.1 / 8.1 = 1.00 | 8.2 / 8.1 = 0.99 | 8.1 / 8.1 = 1.00 |
| `interaction_max_ms` | 24 / 0 | 32 / 0 | 0 / 24 | 0 / 24 | 24 / 16 = 0.67 | 24 / 24 = 1.00 |

The second series with bytecode:

| Metric | Pair 1 | Pair 2 | Pair 3 | Pair 4 | Pair 5 |
| --- | --- | --- | --- | --- | --- |
| `first_row_ms` | 171 / 128 = 0.75 | 163 / 141 = 0.87 | 565 / 710 = 1.26 | 702 / 964 = **1.37** | 1,222 / 495 = 0.41 |
| `walk_elapsed_ms` | 9,346 / 18,017 = **1.93** | 17,041 / 9,627 = 0.56 | 45,446 / 56,080 = 1.23 | 39,794 / 53,861 = **1.35** | 53,560 / 25,186 = 0.47 |
| `tree_fetch_srv_ms` | 26 / 28 = 1.08 | 76 / 27 = 0.36 | 70 / 36 = 0.51 | 78 / 142 = **1.82** | 119 / 49 = 0.41 |
| `load_tree_ms` | 31 / 34 = 1.10 | 83 / 31 = 0.37 | 88 / 46 = 0.52 | 111 / 155 = **1.40** | 164 / 62 = 0.38 |
| `startup_style_server_ms_max` | 39.0 / 22.4 = 0.57 | 16.6 / 17.6 = 1.06 | 25.2 / 31.3 = 1.24 | 213.6 / 258.2 = 1.21 | 300.1 / 77.9 = 0.26 |
| `js_heap_mb` | 29.7 / 10.0 = 0.34 | 18.1 / 31.0 = **1.71** | 16.0 / 12.7 = 0.79 | 13.3 / 14.1 = 1.06 | 9.9 / 13.1 = **1.32** |
| `js_heap_after_gc_mb` | 8.0 / 8.1 = 1.01 | 8.1 / 8.0 = 0.99 | 8.1 / 8.2 = 1.01 | 8.1 / 8.2 = 1.01 | 8.2 / 8.1 = 0.99 |

Without bytecode, `first_row_ms` gave 0.45, 0.90, 0.67, 0.82 and 1.25, and
`walk_elapsed_ms` 0.95, **3.00**, 0.88, 0.95 and 1.14.

These are not results.
Across the eleven pairs with bytecode, first rows are above 1.3x in two and below 0.77x
in five; the root tree’s server time is above in three and below in five; the walk is
above in three and below in three.
A pair straddles a load change as often as not: the second capture of pairs 1 and 2 of
the second series took twice as long to walk as the first, whichever build it was.
The medians say what the scatter says: first rows 224 ms and 224 ms, the root tree’s
fetch and render 55 ms and 56 ms.

Applied as written, the rule stops the release here.
`load_tree_ms`, `tree_fetch_srv_ms` and `walk_elapsed_ms` exceed 1.3x in two or more
pairs, and the explanation offered, load, is an inference from the scatter being
two-sided and from the counts below.
It is not a measurement of a quiet host.

## What does not depend on load

These are the same in every capture of a build, in all three five-pair series, or are
counts of work done.

| Fact | v0.11.0 | Candidate | Reading |
| --- | --- | --- | --- |
| Startup scripts before `DOMContentLoaded` | 20, 171 KB | 20, 173 KB | Inside the gates of 25 and 175 KB; `check_startup_scripts` puts the margin at 2,172 bytes |
| Script transferred by the whole load | 351 KB | 371 KB | 5.7% more; not gated, and not attributed per file in this round |
| Stylesheets transferred | 79 KB | 81 KB |  |
| Largest resource | 84 KB | 89 KB | `app.js`, in the series with bytecode |
| DOM nodes at rest | 1,062 | 1,066 |  |
| Tree rows, lazy stubs, subtree requests | 10, 10, 13 | 10, 10, 13 | 10 subtree requests in one capture of each build without bytecode |
| Tree region repaints | 1 | 1 |  |
| Reserved region shift | 23 px | 23 px | The summary line; open in both |
| Largest inventory delivery batch | 4,096 items | 4,096 items |  |
| Retained heap after collection | 8.0–8.2 MB | 8.0–8.2 MB |  |
| `frame_missing_px` | 220 | 670 | A probe artifact; see below |

### `frame_missing_px` reads 670, and the frame did not change

The metric rose from 220 to 670 in every candidate capture, all of it in
`#preview-pane`, whose shipped height the probe reports as 450 px against a settled 900.

The pane is not half its height at first paint.
The candidate wraps it in `.preview-frame`, a column that holds only the pane.
The probe measures a region’s shipped height by placing a stand-in beside it, and in
that column the stand-in and the pane share the height.
In v0.11.0 the pane’s parent is the page’s row, where a sibling is stretched to the full
height.

Measured in Chrome at 1600x900 on both installed builds, on a small folder:

|  | v0.11.0 | Candidate |
| --- | --- | --- |
| Pane, settled | 900 | 900 |
| Pane holding only the markup the shell ships | 900 | 900 |
| The probe’s stand-in beside the pane | 900 | 450 |
| The pane while the stand-in is present | 900 | 450 |
| A stand-in for the frame, beside the frame | not applicable | 900 |

So the candidate’s value by the metric’s own definition is still 220, all of it the
files panel. The probe needs to place its stand-in beside the frame when the pane has
one. Until it does, this target reads 670 for every build that has the wrapper, and a
later round should not read that as a change in what the shell ships.
It is a roadmap target, not a hard gate, so it does not enter the verdict.

## Start-up work

`startup_pairs.py`, twelve rounds, control then candidate, on a 315-file folder.
Instructions retired, in millions, with bytecode, under a load average of 81–92:

| Metric | v0.11.0 | Candidate | Median pair ratio | Smallest and largest | Pairs above 1.05x | Above 1.3x |
| --- | --- | --- | --- | --- | --- | --- |
| `--show README.md` | 2,425 | 2,530 | 1.037 | 1.00–1.08 | 6 of 12 | 0 |
| `--api /api/tree` | 2,389 | 2,482 | 1.033 | 0.98–1.09 | 5 of 12 | 0 |
| `--version` | 1,882 | 1,869 | 0.993 | 0.95–1.03 | 0 | 0 |
| Server spawn to first `/api` | 2,678 | 2,748 | 1.024 | 0.99–1.08 | 3 of 12 | 0 |
| Shell `/`, first request | 119.4 | 122.4 | 1.033 | 0.94–1.09 | 3 of 12 | 0 |
| Shell `/`, warm | 105.9 | 106.2 | 1.004 | 0.99–1.01 | 0 | 0 |
| `--doctor` | 1,957 | 3,492 | 1.784 | 1.70–1.84 | 12 of 12 | 12 of 12 |

A separate series of fifteen pairs with bytecode, taken by the coordinating session when
the load average was 12–16, agrees: 1.033x, 1.040x, 0.994x, 1.039x and 1.000x for the
first four rows and the warm shell, and 1.779x for `--doctor`. Its wall-clock medians
were `--show` 528 to 577 ms (1.068x), `--api` 1.028x, `--version` 1.026x, the server
0.980x, and `--doctor` 385 to 629 ms (1.533x). Its raw file stayed in that session’s
scratch space, so it corroborates this table and is not part of this round’s record.

Without bytecode the same twelve rounds gave 1.037x, 1.032x, 0.995x, 1.026x and 1.541x
for `--doctor`, on counts three times as large.
exp-037’s counts, 7,401 million for `--show`, are this regime’s: it was measured without
bytecode. Its ratios stand, and its absolute counts describe a start that compiles every
module.

The candidate does 2–4% more work to start, as exp-037 found, and no pair of the four
start-up metrics exceeds 1.1x.

`--doctor` exceeds the tolerance in every pair.
exp-037 gives the cause: since `567d6b19` it validates the packaged cache record
contracts, which imports the schema libraries and regenerates each schema.
With bytecode the ratio is larger than exp-037’s 1.54x, because the added work is the
same and the rest of the command is a third of what it was.
By the rule this stops a release until it is fixed or accepted, and accepting it is the
maintainer’s decision, not this record’s.

Wall time in this series is not a result: `--show` pairs ran from 0.69x to 1.99x.

## Walk work

The walk is what the browser half waits on, and its wall time above is unusable.
Five pairs counted it instead, on `project-10` with bytecode, alternating the order,
under a load average of 48–97:

| Metric | v0.11.0 | Candidate | Median pair ratio | Smallest and largest |
| --- | --- | --- | --- | --- |
| `--walk --format json`, instructions (millions) | 50,664 | 50,082 | 0.991 | 0.92–1.00 |
| `--walk`, CPU time | 9.83 s | 9.63 s | 1.010 | 0.85–1.03 |
| `--walk`, peak footprint | 311.6 MB | 310.5 MB | 0.996 | 0.98–1.02 |
| Server, spawn to a completed walk, instructions (millions) | 38,759 | 38,391 | 0.979 | 0.87–1.11 |
| Server, CPU time to a completed walk | 8.13 s | 7.86 s | 0.992 | 0.89–1.15 |

The server rows include the progress requests that watched for completion, 13 to 46 of
them depending on how long the walk took, so they spread more than the one-shot rows.

The candidate does not do more work to walk this tree.
The instrument is a scratch script built on `startup_pairs.py`’s counter and is not
committed; the walk needs a committed one before a later round leans on this.

## Backend timings

`compare_builds` with bytecode, control / candidate = ratio.
Bold is above 1.3x.

First run, load average 17–22:

| Metric | Pair 1 | Pair 2 | Pair 3 | Pair 4 | Pair 5 |
| --- | --- | --- | --- | --- | --- |
| `spawn_to_serving` s | 0.977 / 1.533 = **1.57** | 0.910 / 0.969 = 1.06 | 0.865 / 0.837 = 0.97 | 0.753 / 0.517 = 0.69 | 0.463 / 0.501 = 1.08 |
| `first_row` s | 0.054 / 0.147 = **2.72** | 0.035 / 0.122 = **3.49** | 0.053 / 0.103 = **1.94** | 0.014 / 0.015 = 1.07 | 0.012 / 0.012 = 1.00 |
| `index_done` s | 14.87 / 17.71 = 1.19 | 13.95 / 15.45 = 1.11 | 14.50 / 13.22 = 0.91 | 5.53 / 4.75 = 0.86 | 4.50 / 11.72 = **2.60** |
| `peak_rss_mb` | 178.7 / 180.0 = 1.01 | 182.6 / 185.7 = 1.02 | 177.0 / 181.8 = 1.03 | 182.0 / 182.7 = 1.00 | 180.6 / 183.6 = 1.02 |
| Tally-overlap progress max ms | 125.7 / 70.1 = 0.56 | 215.3 / 42.1 = 0.20 | 65.8 / 62.7 = 0.95 | 56.3 / 40.9 = 0.73 | 75.0 / 174.0 = **2.32** |

Second run, load average 25–32:

| Metric | Pair 1 | Pair 2 | Pair 3 | Pair 4 | Pair 5 |
| --- | --- | --- | --- | --- | --- |
| `spawn_to_serving` s | 1.151 / 1.571 = **1.36** | 0.945 / 0.875 = 0.93 | 1.603 / 1.077 = 0.67 | 1.047 / 1.164 = 1.11 | 0.764 / 0.727 = 0.95 |
| `first_row` s | 0.027 / 0.041 = **1.52** | 0.045 / 0.042 = 0.93 | 0.040 / 0.042 = 1.05 | 0.099 / 0.219 = **2.21** | 0.028 / 0.018 = 0.64 |
| `index_done` s | 15.29 / 14.05 = 0.92 | 15.22 / 16.40 = 1.08 | 14.93 / 12.78 = 0.86 | 12.97 / 8.94 = 0.69 | 6.95 / 9.13 = **1.31** |
| `peak_rss_mb` | 182.0 / 183.5 = 1.01 | 177.1 / 179.0 = 1.01 | 181.5 / 181.7 = 1.00 | 181.2 / 182.8 = 1.01 | 179.8 / 182.6 = 1.02 |
| Tally-overlap progress max ms | 206.6 / 69.6 = 0.34 | 96.4 / 128.1 = **1.33** | 118.2 / 59.0 = 0.50 | 109.2 / 45.8 = 0.42 | 105.1 / 50.6 = 0.48 |

Peak memory is 1.00–1.03x in every pair, and that is a result.

Backend `first_row` is the one timing here that leans one way.
It is above 1.3x in five of these ten pairs and in five of the ten taken without
bytecode, and below 0.77x in one and three.
In the two pairs where both builds answered in under 20 ms it is 1.07x and 1.00x. The
one-shot `--api /api/tree`, which makes the same first request, retires 1.03x the
instructions, so the candidate is not doing two or three times the work to produce first
rows. What the candidate may do is wait longer for a thread under contention, and this
round cannot say whether it does.
The README makes a first-row regression past the tolerance a reason not to accept, so
this stays open: the backend pairs are owed on a quiet machine with the browser series.

## What did not move

Retained heap, peak server memory, the tree’s rendered size, the number of requests a
load makes, the delivery batch bound, and the single paint of the tree region are the
same in both builds.
Every responsiveness figure is zero or far inside its gate for both.
The candidate’s layout-shift score was 0 in every capture; the control’s was 0.005 in
the series without bytecode and 0 with it.

## What this does not establish

It does not establish that v0.12 is as fast as v0.11.0 for a reader.
The wall-clock comparison was taken on a host where the released build fails its own
gate, and the pair ratios scatter by an order of magnitude.

It does not establish that the candidate passes the hard gates.
In its eight captures taken at a load average below 30 it passed every one, with first
rows at 115–323 ms, and eight captures on a busy host are not the five quiet interleaved
pairs the release rule asks for.

It did not measure the 300,000-file flat corpus.
exp-036 carried that pass forward, and it is still owed; the disk had 10–14 GB free and
the corpus was not built.

It did not measure a Git source.
Everything here is a folder on disk, which is the only subject v0.11.0 can serve.
The pinned-revision path that v0.12 adds has no control to compare with, and its own
first-row and responsiveness numbers are not in this loop.

It did not exercise repeated page loads in one tab.
Each capture is one load in a fresh profile, so a defect that needs several loads in one
tab to appear is outside what this loop can see, in either build.

It is not the release comparison.
`c16912f8` is not the commit that will be tagged; more changes are stacked above it.

## Owed before a release

On a host whose load average stays below about 10 for the whole series, on the commit to
be tagged, against the same v0.11.0 wheel and with bytecode in both environments:

1. Five interleaved headed pairs on `project-10`. Every candidate capture must pass the
   hard gates, and the pair rule is applied at 1.3x, or at 1.1x if the host is quiet
   enough to claim it.
2. Five `compare_builds` pairs, read for backend `first_row` in particular.
3. The 300,000-file flat-stress pass against `performance-budgets-flat-stress.toml`.
4. A decision on `--doctor`: accept 1.78x the instructions and about 1.5x the wall time
   as the cost of validating the cache record contracts, or move that check.
5. The probe’s stand-in fixed for a wrapped preview pane, so `frame_missing_px` reads
   what it names.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
