---
title: The v0.9 candidate preserves release correctness and responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-021
  title: The v0.9 candidate preserves release correctness and responsiveness
  date: "2026-08-31"
  hypotheses: []
  subject:
    corpus: fingerprinted project-shaped tree tree-a1a7991c
    corpus_files: 113350
    corpus_dirs: 6520
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.8.0, built from its tag
    candidate: exact installed wheel from 3160965
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 1.229
      candidate_median: 1.162
      control_range: [1.181, 1.452]
      candidate_range: [1.066, 1.281]
      change_pct: -5.5
      overlapping: true
    - metric: backend_index_done_s
      control_median: 13.369
      candidate_median: 13.372
      control_range: [12.744, 13.955]
      candidate_range: [12.666, 15.313]
      change_pct: 0.0
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 179.2
      candidate_median: 180.3
      control_range: [178.6, 186.4]
      candidate_range: [175.0, 190.7]
      change_pct: 0.6
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 287
      candidate_median: 325
      control_range: [230, 332]
      candidate_range: [293, 450]
      change_pct: 13.2
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 204
      candidate_median: 200
      control_range: [184, 212]
      candidate_range: [180, 296]
      change_pct: -2.0
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
      The candidate serves 809 DOM nodes against the control's 1027, which is the
      file-type registry supplying tree identity rather than the retired matcher table.
      Backend equivalence reports zero row differences and two tally differences, both
      in file_type_registry: schema_version 3 vs 4 and its fingerprint. That is the
      declared v4 schema bump, not a drift, so the run is accepted explicitly rather
      than read as valid. The roadmap targets still open — frame_missing_px 220,
      reserved_region_shift_px 23, fcp over 200 ms — are open on both builds.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The candidate returns identical ordered rows on an unchanged corpus, differs in
      tallies only where the release declares a schema bump, holds backend timing and
      memory inside overlapping ranges, and passes every hard browser budget across
      three admissible profiles. Browser first row is nominally 13% slower with ranges
      that overlap by a wide margin, which the accept rule does not treat as a result.
    commit: 3160965
---
# exp-021: the v0.9 candidate preserves release correctness and responsiveness

The release comparison required before tagging: the previous release against the
candidate, both as installed console scripts, on one unchanged corpus.

## What this round also fixed in the harness

Two things blocked it, and both are now process rather than lore.

**There was no way to build the corpus.** `.bench/` is gitignored and machine-local, and
the README named `.bench/project-10` throughout without saying how it comes to exist.
A fresh checkout could not run any of this.
Building it is now the first section of the README.

**A reused label silently pooled two corpora.** The first attempt labelled the control
`release-v0.8.0`, which is what exp-020 used in August on a different tree.
`compare` pooled six runs across two corpora and reported a plausible first-row
regression that was entirely the older round’s smaller tree — 67,290 files against
113,350. Nothing in the output contradicted it.

`compare` now refuses a label spanning more than one corpus, and refuses two labels
measured on different ones.
The README’s advice to label with the hypothesis was already there; it is now enforced,
because the failure looks like an ordinary result.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
