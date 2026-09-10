---
title: The final candidate restores bounded stream continuity
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-031
  title: The final candidate restores bounded stream continuity
  date: "2026-09-10"
  hypotheses: []
  subject:
    corpus: fingerprinted synthetic tree tree-6dbe6989
    corpus_files: 60000
    corpus_dirs: 1105
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: exact installed v0.9.1 release built from tag commit 16211ccb
    candidate: exact installed wheel from e841f783
    record: five interpreter-matched backend pairs and five headed-browser profiles per condition
  results:
    - metric: backend_spawn_to_serving_s
      control_median: 0.531
      candidate_median: 0.600
      control_range: [0.484, 0.583]
      candidate_range: [0.510, 0.946]
      change_pct: 13.0
      overlapping: true
    - metric: backend_first_row_s
      control_median: 0.277
      candidate_median: 0.014
      control_range: [0.269, 0.286]
      candidate_range: [0.013, 0.021]
      change_pct: -94.9
      overlapping: false
    - metric: backend_index_done_s
      control_median: 1.871
      candidate_median: 1.615
      control_range: [1.608, 2.178]
      candidate_range: [1.606, 1.909]
      change_pct: -13.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 120.3
      candidate_median: 114.1
      control_range: [119.3, 121.4]
      candidate_range: [112.7, 121.5]
      change_pct: -5.2
      overlapping: true
    - metric: browser_ttfb_ms
      control_median: 13
      candidate_median: 13
      control_range: [11, 20]
      candidate_range: [12, 67]
      change_pct: 0.0
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 118
      candidate_median: 192
      control_range: [111, 238]
      candidate_range: [186, 537]
      change_pct: 62.7
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 112
      candidate_median: 232
      control_range: [100, 172]
      candidate_range: [224, 404]
      change_pct: 107.1
      overlapping: false
    - metric: browser_api_transfer_kb
      control_median: 177
      candidate_median: 166
      control_range: [90, 240]
      candidate_range: [140, 208]
      change_pct: -6.2
      overlapping: true
    - metric: browser_event_stream_overflows_per_run
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      change_pct: 0.0
      overlapping: true
    - metric: browser_tree_region_repaints
      control_median: 1
      candidate_median: 1
      control_range: [1, 1]
      candidate_range: [1, 1]
      change_pct: 0.0
      overlapping: true
    - metric: browser_frame_missing_px
      control_median: 269
      candidate_median: 269
      control_range: [269, 269]
      candidate_range: [269, 269]
      change_pct: 0.0
      overlapping: true
    - metric: browser_long_tasks
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      change_pct: 0.0
      overlapping: true
    - metric: browser_animation_frame_max_ms
      control_median: 0
      candidate_median: 160
      control_range: [0, 78]
      candidate_range: [156, 310]
      overlapping: false
    - metric: browser_file_catalog_incomplete
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      change_pct: 0.0
      overlapping: true
    - metric: browser_hard_gate_pass_rate_pct
      control_median: 100
      candidate_median: 100
      control_range: [100, 100]
      candidate_range: [100, 100]
      change_pct: 0.0
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      The comparison uses standard CPython 3.14.7 for both installed builds. A first
      candidate environment accidentally selected free-threaded 3.14 and was discarded
      before this record. One admissible candidate browser run caught a system-wide slow
      interval: its walk took 7.095 seconds and its first row took 537 ms; it remains in
      the range and still passes every hard budget. No candidate run reports a queue
      overflow, incomplete catalog, long task, blocking time, network failure, preview
      failure, or page exception.
  verdict:
    decision: accepted
    primary_metric: browser_event_stream_overflows_per_run
    reason: >-
      All five candidate profiles retain one tree paint, the release frame shape, one
      corpus-sized catalog delivery, and an uninterrupted bounded stream. Exact backend
      rows and tallies match the release, and every candidate run passes the hard
      responsiveness gate. FCP remains a repeatable 232 ms median against a 200 ms roadmap
      target, with one nonblocking 310 ms animation frame in the system-slow run. That
      residual active-discovery contention is retained as an explicit optimization task;
      a disposable fourfold increase in cooperative-yield frequency made both startup and
      scan completion worse. It does not justify adding a riskier scheduler change to the
      release candidate.
    commit: e841f783
---
# exp-031: the final candidate restores bounded stream continuity

The final candidate removes the redundant per-path invalidation that rejected exp-030.
All five candidate server logs are free of bounded-queue overflows, every Quick File
catalog is complete, and each profile applies roughly one corpus of inventory entries
instead of recovering through repeated full snapshots.
Median API transfer falls from 177 KiB in the release to 166 KiB in the candidate; the
ranges overlap, so this is confirmation that the refetch amplification disappeared, not
a throughput claim.

The installed-console-script backend comparison is exact.
It finds no ordered-row or tally difference on the unchanged physical corpus.
The candidate returns its first nonempty tree page in 14 ms rather than 277 ms.
Index-completion and resident-memory ranges overlap, and tally work does not delay an
unrelated progress request beyond the release range.

The browser retains the fixes from the rejected rounds: one whole-tree paint rather than
two, the same 269-pixel initial Files region as v0.9.1, no incomplete catalogs, and no
continuity recovery.
There are no Long Tasks, measured blocking time, network failures, rendered-preview
errors, or page exceptions in either condition.
Every run passes the hard performance gate.

Cold FCP during active discovery remains slower: 232 ms at the median versus 112 ms for
v0.9.1, above the 200 ms roadmap target but well inside the release gate.
The first-row ranges overlap and the candidate median is 192 ms, below its 500 ms
target. One candidate profile coincided with a broad system slowdown—7.095 seconds to
finish the walk, 67 ms to first byte, and 537 ms to first row—and remains in the
accepted evidence rather than being discarded.
Its 310 ms animation frame attributes no script, render, or blocking duration.

The delay follows active provider discovery, not dependency versions or KPress loading.
Earlier cross-matrix and settled-index diagnostics established that boundary.
A final disposable trial yielded every 16 entries instead of every 64; its two first-row
results worsened to 258 and 367 ms, FCP worsened to 292 and 400 ms, and its walks slowed
to 4.071 and 4.402 seconds.
The exact wheel was restored after rejecting that trial.
The remaining provider bookkeeping is therefore an optimization follow-up, not a reason
to put an unmeasured scheduling change into this release.

The release conclusion is narrower than performance parity.
The candidate is semantically equivalent, bounded, complete, repaint-stable, and inside
every hard budget; it trades a measured cold-paint delay during a large active scan for
the provider-neutral inventory engine and much earlier backend row availability.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
