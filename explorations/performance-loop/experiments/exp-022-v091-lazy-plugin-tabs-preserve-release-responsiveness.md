---
title: The v0.9.1 lazy-plugin-tab fix preserves release correctness and responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-022
  title: The v0.9.1 lazy-plugin-tab fix preserves release correctness and responsiveness
  date: "2026-09-01"
  hypotheses: []
  subject:
    corpus: fingerprinted project-shaped tree tree-0eb8a51b
    corpus_files: 113430
    corpus_dirs: 6520
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.9.0, built from its tag
    candidate: exact installed wheel from 929130c1
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 1.188
      candidate_median: 1.147
      control_range: [0.834, 1.817]
      candidate_range: [1.103, 1.271]
      change_pct: -3.5
      overlapping: true
    - metric: backend_index_done_s
      control_median: 11.762
      candidate_median: 11.539
      control_range: [11.076, 23.826]
      candidate_range: [10.836, 11.958]
      change_pct: -1.9
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 179.2
      candidate_median: 179.8
      control_range: [179.0, 188.2]
      candidate_range: [179.5, 187.9]
      change_pct: 0.3
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 145
      candidate_median: 136
      control_range: [121, 152]
      candidate_range: [93, 150]
      change_pct: -6.2
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 120
      candidate_median: 112
      control_range: [120, 132]
      candidate_range: [96, 112]
      change_pct: -6.7
      overlapping: false
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
      The production delta changes one function-scoped lazy-view callback binding to a
      block-scoped binding. Backend equivalence reports zero ordered-row and zero tally
      differences on the unchanged corpus. The browser comparison passes every hard
      budget. The two existing roadmap misses, frame_missing_px 220 and
      reserved_region_shift_px 23, are identical across both builds. A separate real
      plugin smoke proves that each inactive view now mounts its own renderer.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The candidate is semantically identical at the backend boundary, keeps timing and
      memory inside the release ranges, and passes every hard browser budget across
      three admissible profiles. First contentful paint is nominally faster, but that
      improvement is not the purpose of this patch and is not needed for acceptance.
    commit: 929130c1
---
# exp-022: the v0.9.1 lazy-plugin-tab fix preserves release correctness and responsiveness

This is the release comparison required before tagging the v0.9.1 patch: the exact
v0.9.0 release against the installed candidate wheel on one unchanged corpus.

The backend comparison completed five alternating pairs and found no row or tally
differences. Three cold browser profiles per condition passed every hard responsiveness
and correctness budget.
The static script transfer was identical, and the existing layout roadmap misses were
unchanged.

The generic release probe does not select an inactive third-party plugin tab.
That behavior was checked separately in a real browser with an SDK 0.5 plugin containing
four views: the default, Queries, and URLs render independently after the fix, and the
Source view remains unmounted until selected.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
