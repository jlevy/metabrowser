---
title: The v0.9.1 final candidate preserves release correctness and responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-023
  title: The v0.9.1 final candidate preserves release correctness and responsiveness
  date: "2026-09-01"
  hypotheses: []
  subject:
    corpus: fingerprinted local run-data tree tree-91d23f89
    corpus_files: 39975
    corpus_dirs: 11593
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact installed PyPI v0.9.0 release
    candidate: exact installed wheel from f1d36447
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 1.599
      candidate_median: 1.311
      control_range: [1.049, 1.613]
      candidate_range: [1.055, 1.586]
      change_pct: -18.0
      overlapping: true
    - metric: backend_index_done_s
      control_median: 15.115
      candidate_median: 14.902
      control_range: [13.063, 29.019]
      candidate_range: [13.616, 30.162]
      change_pct: -1.4
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 216.4
      candidate_median: 225.1
      control_range: [210.3, 264.4]
      candidate_range: [210.5, 243.6]
      change_pct: 4.0
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 161
      candidate_median: 186
      control_range: [147, 278]
      candidate_range: [166, 272]
      change_pct: 15.5
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 136
      candidate_median: 132
      control_range: [112, 192]
      candidate_range: [128, 232]
      change_pct: -2.9
      overlapping: true
    - metric: browser_hard_gate_pass_rate_pct
      control_median: 100
      candidate_median: 100
      control_range: [100, 100]
      candidate_range: [100, 100]
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      The production delta contains two narrow correctness fixes: each lazy plugin tab
      closes over its own renderer, and folder rollups preserve and compare the complete
      file-type registry identity. Backend equivalence reports zero ordered-row and zero
      tally differences on an unchanged corpus. Every browser run passes the hard gate
      with no network, rendered-preview, or page errors and identical script transfer.
      One candidate profile records fcp_ms 232 against the aspirational 200 ms target,
      but the candidate median is lower and the ranges overlap, so it is not a
      repeatable wrong-way result. The existing frame and reserved-region roadmap misses
      remain unchanged.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The exact final candidate is semantically identical at the backend boundary,
      preserves release timing and memory ranges, and passes every hard browser budget
      across three admissible profiles. No measured difference is both repeatable and in
      the wrong direction.
    commit: f1d36447
---
# exp-023: the v0.9.1 final candidate preserves release correctness and responsiveness

This is the final release comparison required before tagging v0.9.1: the exact v0.9.0
release against the installed wheel from `f1d36447` on one unchanged corpus.
Both installed environments were staged outside a Git checkout so their displayed
versions came only from package metadata rather than the enclosing repository state.

Five alternating backend pairs found no ordered-row or tally differences.
Three cold browser profiles per condition passed every hard responsiveness and
correctness budget. The timing and memory ranges overlap, the static script transfer is
identical, and no profile records a network, rendered-preview, or page error.

The candidate’s 132 ms first-contentful-paint median is slightly below the release’s 136
ms median, but one candidate profile took 232 ms and missed the 200 ms roadmap target.
That is not a measured improvement or a repeatable regression: the ranges overlap, and
the hard gate passes.
The two existing layout roadmap misses are unchanged.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
