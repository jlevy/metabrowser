---
title: The completed catalog is rejected on duplicate invalidations
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-030
  title: The completed catalog is rejected on duplicate invalidations
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
    candidate: exact installed wheel from 777acf17
    record: five backend pairs and five headed-browser profiles per condition
  results:
    - metric: backend_first_row_s
      control_median: 0.269
      candidate_median: 0.013
      control_range: [0.267, 0.272]
      candidate_range: [0.012, 0.043]
      change_pct: -95.2
      overlapping: false
    - metric: backend_index_done_s
      control_median: 1.586
      candidate_median: 1.341
      control_range: [1.583, 1.599]
      candidate_range: [1.335, 1.649]
      change_pct: -15.4
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 119.5
      candidate_median: 114.0
      control_range: [118.2, 121.6]
      candidate_range: [112.2, 120.0]
      change_pct: -4.6
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 109
      candidate_median: 207
      control_range: [106, 159]
      candidate_range: [178, 249]
      change_pct: 89.9
      overlapping: false
    - metric: browser_fcp_ms
      control_median: 104
      candidate_median: 220
      control_range: [96, 132]
      candidate_range: [208, 288]
      change_pct: 111.5
      overlapping: false
    - metric: browser_api_transfer_kb
      control_median: 188
      candidate_median: 626
      control_range: [152, 202]
      candidate_range: [358, 711]
      change_pct: 233.0
      overlapping: false
    - metric: browser_event_stream_overflows_per_run
      control_median: 0
      candidate_median: 1
      control_range: [0, 0]
      candidate_range: [1, 1]
      overlapping: false
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
      Backend equivalence reports zero ordered-row and tally differences on an unchanged
      corpus. Both conditions preserve one tree paint and the same 269-pixel Files-region
      result, with no long tasks, blocking time, network failures, preview failures, or
      page exceptions. All hard budgets pass, but every candidate server log records one
      bounded event-stream queue overflow.
  verdict:
    decision: rejected
    primary_metric: browser_event_stream_overflows_per_run
    reason: >-
      The terminal progress fallback repairs catalog completeness, but every candidate
      profile still overflows its bounded stream queue and refetches authoritative state.
      Static tracing found that each changed path emits an unconsumed
      projection.invalidate record before the authoritative batched fs.change record,
      even though fs.change already invalidates every affected browser projection. Remove
      the duplicate event model and rerun the exact candidate.
    commit: 777acf17
---
# exp-030: the completed catalog is rejected on duplicate invalidations

The terminal progress fallback added after exp-029 closes the catalog-completion gap.
Every candidate profile ends with all 60,000 eligible files in Quick File, and the
performance harness passes every hard correctness and responsiveness gate.
That makes the remaining stream churn visible instead of letting incomplete state hide
it.

Every candidate server log records one bounded event-stream queue overflow; none of the
five release logs does.
Four candidate profiles deliver the full catalog more than once, and even the smallest
candidate API transfer is larger than the largest release transfer.
The browser ends correct because the resynchronization and terminal refetch paths work,
but correctness recovery is not a substitute for avoiding a redundant continuity gap.

The stream projected one `projection.invalidate` record for every dirty path before its
bounded `fs.change` batch.
No browser code subscribed to that event, while `fileStoreApplyChange` already
invalidates subtree caches and file previews, applies directory rollups, and notifies
SDK subscribers from the same changed paths.
The unused event therefore multiplied queue occupancy without carrying a distinct state
transition.

The follow-up removes both unused projection event models and treats `fs.change` as the
single changed-path invalidation contract.
A deterministic regression test places a multi-path change in a two-slot connection
queue: one filesystem batch and its catalog companion must fit without detaching the
subscriber.

The exact installed-console-script backend comparison still returns identical ordered
rows and tallies. Its first row is materially earlier, while the index-completion and
memory ranges overlap the release.
The browser startup regression remains separately visible and must be assessed again
only after the stream fix removes resynchronization as a confounder.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
