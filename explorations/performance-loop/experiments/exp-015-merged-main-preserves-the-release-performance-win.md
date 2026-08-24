---
title: Merged main preserves the release performance win
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-015
  title: Merged main preserves the release performance win
  date: "2026-08-24"
  hypotheses:
    - H58
  subject:
    corpus: project-shaped tree tree-2962a2a1
    corpus_files: 247063
    corpus_dirs: 31201
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 4
    interleaved: true
    control: globally installed v0.6.0 at tag v0.6.0
    candidate: installed wheel from merged main bae51fd
    record: five backend pairs and eight browser profiles summarized in this experiment
  results:
    - metric: backend_spawn_to_serving_s
      control_median: 0.722
      candidate_median: 0.872
      control_range: [0.678, 0.824]
      candidate_range: [0.762, 1.831]
      change_pct: 20.8
      overlapping: true
    - metric: backend_first_row_s
      control_median: 3.674
      candidate_median: 1.388
      control_range: [3.402, 4.058]
      candidate_range: [1.068, 1.561]
      change_pct: -62.2
      overlapping: false
    - metric: backend_index_done_s
      control_median: 38.722
      candidate_median: 14.879
      control_range: [35.554, 39.832]
      candidate_range: [14.197, 17.581]
      change_pct: -61.6
      overlapping: false
    - metric: backend_peak_rss_mb
      control_median: 182.1
      candidate_median: 177.5
      control_range: [169.3, 184.6]
      candidate_range: [172.8, 185.2]
      change_pct: -2.5
      overlapping: true
    - metric: browser_hard_gate_pass_rate_pct
      control_median: 0
      candidate_median: 100
      control_range: [0, 0]
      candidate_range: [100, 100]
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 652.5
      candidate_median: 231.5
      control_range: [320, 1093]
      candidate_range: [168, 1097]
      change_pct: -64.5
      overlapping: true
    - metric: browser_load_tree_ms
      control_median: 147
      candidate_median: 17
      control_range: [17, 843]
      candidate_range: [10, 42]
      change_pct: -88.4
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 164
      candidate_median: 178
      control_range: [152, 252]
      candidate_range: [132, 996]
      change_pct: 8.5
      overlapping: true
    - metric: browser_lcp_ms
      control_median: 362
      candidate_median: 178
      control_range: [252, 392]
      candidate_range: [132, 996]
      change_pct: -50.8
      overlapping: true
    - metric: browser_total_blocking_time_ms
      control_median: 6994
      candidate_median: 0
      control_range: [0, 18255]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: true
    - metric: browser_long_task_max_ms
      control_median: 2474.5
      candidate_median: 0
      control_range: [0, 6027]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: true
    - metric: browser_interaction_max_ms
      control_median: 204
      candidate_median: 20
      control_range: [24, 640]
      candidate_range: [0, 24]
      change_pct: -90.2
      overlapping: true
    - metric: browser_main_thread_blocked_pct
      control_median: 40.25
      candidate_median: 0
      control_range: [0, 90.3]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: true
    - metric: browser_startup_script_requests
      control_median: 74
      candidate_median: 22
      control_range: [74, 74]
      candidate_range: [22, 22]
      change_pct: -70.3
      overlapping: false
    - metric: browser_startup_script_transfer_kb
      control_median: 332
      candidate_median: 154
      control_range: [332, 332]
      candidate_range: [154, 154]
      change_pct: -53.6
      overlapping: false
    - metric: browser_request_count
      control_median: 141
      candidate_median: 103
      control_range: [133, 157]
      candidate_range: [88, 109]
      change_pct: -27.0
      overlapping: false
    - metric: browser_transfer_kb
      control_median: 657
      candidate_median: 521.5
      control_range: [516, 767]
      candidate_range: [469, 599]
      change_pct: -20.6
      overlapping: true
    - metric: browser_heap_after_gc_mb
      control_median: 6.3
      candidate_median: 6.15
      control_range: [5.4, 6.7]
      candidate_range: [5.7, 6.6]
      change_pct: -2.4
      overlapping: true
    - metric: browser_dom_nodes
      control_median: 2449
      candidate_median: 1025
      control_range: [1039, 2449]
      candidate_range: [1025, 1165]
      change_pct: -58.1
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes:
      - a release older than the profiler needs a measurement-only recorder adapter
      - starting the next server before recording finishes can replace pending provenance
    notes: >-
      This is a post-merge validation of the exact main commit, not another product
      change. The comparison framework now has an atomic JSON output for backend runs,
      a documented previous-release procedure, and a release-checklist entry. Browser
      records remain append-only in the performance ledger. No production compatibility
      layer or dependency was added.
  verdict:
    decision: accepted
    primary_metric: every candidate run passes the hard responsiveness and correctness gates
    reason: >-
      Merged main returns the first backend row and completes indexing about 62 percent
      sooner with identical ordered rows and tallies. All four candidate browser runs
      pass every hard gate, with no Long Task, Total Blocking Time, blocked main-thread
      share, fetch error, or incomplete catalog. The release has severe intermittent
      stalls. Paint and process-start ranges overlap because one candidate cold start is
      a tail outlier, so those metrics show no detected difference rather than a loss.
---
# Merged main preserves the release performance win

## Question

After the performance pull request merged, does the exact `main` build retain the
backend improvement without making a large directory tree less responsive than the
previous release?

Yes. The merged build returns backend rows and completes the index about 62% sooner, and
every browser run remains within the responsiveness gates while the release still shows
intermittent multi-second stalls.

This run is recorded separately from the pull-request measurements in
[exp-014](exp-014-backend-volume-stops-controlling-browser-responsiveness.md).
It checks the exact merge result, catches merge or build differences, and establishes
the form of the previous-release comparison that belongs in future release work.

## Exact provenance and method

The control is the globally installed console script at tag `v0.6.0`, which reports
`metab 0.6.0`. The candidate is a wheel built from merged `main` commit `bae51fd`, which
reports `metab 0.6.1.dev68+bae51fd`.

The release predates the current navigation-time recorder.
For its browser runs only, a temporary instrumented copy replaced `perf.js` and
connected the current recorder to the release namespace.
The release application and server remained exact.
This was a measurement adapter, not a production compatibility layer.
Releases that include the current framework can be measured directly.

Both builds used the same project-shaped corpus: 247,063 physical files in 31,201
directories. The backend comparator alternated five runs per build, fingerprinted the
corpus before and after, and compared ordered navigation rows and tallies before
admitting the timings.
The browser comparison alternated four fresh-profile, fresh-port runs per build in a
visible 1600×900 headed Chrome window.
Trusted input continued from first row through client quiescence.

One release capture was excluded because the following server run replaced its pending
provenance before recording finished.
Its serialized rerun replaced it.
This is a measurement-process failure, not a product sample; future runs must wait for
the `recorded` confirmation before starting the next server.

## Backend result

The corpus fingerprint was unchanged, both semantic difference counts were zero, and
neither build reported an error.

| measure | v0.6.0 median (range) | merged main median (range) | result |
| --- | ---: | ---: | --- |
| process to serving | 0.722 s (0.678–0.824) | 0.872 s (0.762–1.831) | no detected difference |
| first navigation row | 3.674 s (3.402–4.058) | **1.388 s (1.068–1.561)** | 62% sooner |
| index complete | 38.722 s (35.554–39.832) | **14.879 s (14.197–17.581)** | 62% sooner |
| peak RSS | 182.1 MB (169.3–184.6) | 177.5 MB (172.8–185.2) | no detected difference |

Process startup includes one 1.831-second candidate sample, and its range overlaps the
release. The evidence supports neither a startup win nor a startup regression.

## Browser result

The current build passes every hard responsiveness and correctness gate in all four
runs. It records no Long Task, no Total Blocking Time, no blocked main-thread share, no
fetch failure, and no incomplete catalog.
Inventory delivery stays in bounded slices: its callback maximum is 3.5 ms (2–6), and
the work consumes 0.35% (0.3–0.4) of the measured window.

The release fails the current policy in all four runs.
Some failures are expected because the older application lacks newer readiness and
attribution surfaces, but the direct responsiveness signals are conclusive in two runs:
Long Tasks reach 6,027 ms, Total Blocking Time reaches 18,255 ms, interactions reach 640
ms, and the main thread is blocked for as much as 90.3% of the observed window.
This variability is why the gate checks every candidate run instead of trusting a
median.

| measure | v0.6.0 median (range) | merged main median (range) | result |
| --- | ---: | ---: | --- |
| hard-gate passes | 0 of 4 | **4 of 4** | candidate passes every run |
| first row | 652.5 ms (320–1,093) | 231.5 ms (168–1,097) | lower median; tail overlaps |
| tree fetch | 147 ms (17–843) | 17 ms (10–42) | lower median; ranges overlap |
| FCP | 164 ms (152–252) | 178 ms (132–996) | no detected difference |
| LCP | 362 ms (252–392) | 178 ms (132–996) | lower median; tail overlaps |
| Total Blocking Time | 6,994 ms (0–18,255) | **0 ms (0–0)** | no candidate blocking |
| longest Long Task | 2,474.5 ms (0–6,027) | **0 ms (0–0)** | no candidate Long Task |
| worst interaction | 204 ms (24–640) | **20 ms (0–24)** | every candidate run under gate |
| blocked main-thread share | 40.25% (0–90.3) | **0% (0–0)** | no candidate blocking |
| startup scripts | 74 | **22** | 70% fewer |
| startup JavaScript | 332 KB | **154 KB** | 54% less |
| all requests | 141 (133–157) | **103 (88–109)** | 27% fewer |
| all transfer | 657 KB (516–767) | 521.5 KB (469–599) | lower median; ranges overlap |
| heap after controlled GC | 6.3 MB (5.4–6.7) | 6.15 MB (5.7–6.6) | no detected difference |
| DOM nodes | 2,449 (1,039–2,449) | 1,025 (1,025–1,165) | lower median; ranges overlap |

One candidate cold start produces the 996 ms paint and 1,097 ms first-row tail.
It does not block the UI or cross a hard budget, but it prevents a claim that every
individual paint is faster.
The tail remains tracked as `mb-bcdu`; repeated ranges, not one favorable median, decide
whether it is a reproducible regression.

## What future release comparisons retain

The durable result has three layers:

- `devtools.compare_builds --output` writes the complete backend runs, fingerprints,
  semantic comparison, build paths, versions, timings, and validation errors to an
  atomic JSON report under `.bench/`;
- browser `capture --record` keeps normalized, provenance-bearing profiles in the
  append-only performance ledger, while full diagnostic profiles remain under `.bench/`;
  and
- an `exp-NNN` document such as this one commits the build identities, method, ranges,
  limits, and verdict, then `run.py report` adds it to the generated history.

Machine reports retain local executable and corpus paths, so they do not belong in the
public repository. Attach them to the pull request or bug when the raw evidence is
needed.
The experiment record uses an opaque corpus label and immutable build refs, so it
is safe and useful to keep.

## Verdict

**Accepted.** Merged `main` preserves the backend speedup and removes the release’s
intermittent frontend stalls.
No candidate run violates a responsiveness, startup, network, readiness, or correctness
gate. Startup and paint tail variance remains a named optimization target rather than
being hidden inside the successful result.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
