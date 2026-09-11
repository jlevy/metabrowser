---
title: The first v0.9.1-to-current candidate is rejected on a second root repaint
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-027
  title: The first v0.9.1-to-current candidate is rejected on a second root repaint
  date: "2026-09-09"
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
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.9.1 release built from tag commit 16211ccb
    candidate: exact installed wheel from f097c667
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 0.273
      candidate_median: 0.013
      control_range: [0.010, 0.281]
      candidate_range: [0.012, 0.016]
      change_pct: -95.2
      overlapping: true
    - metric: backend_index_done_s
      control_median: 1.606
      candidate_median: 1.354
      control_range: [1.602, 1.909]
      candidate_range: [1.345, 1.873]
      change_pct: -15.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 120.0
      candidate_median: 114.1
      control_range: [119.2, 121.5]
      candidate_range: [112.9, 114.7]
      change_pct: -4.9
      overlapping: false
    - metric: browser_ttfb_ms
      control_median: 12
      candidate_median: 77
      control_range: [11, 13]
      candidate_range: [76, 132]
      change_pct: 541.7
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 109
      candidate_median: 151
      control_range: [107, 185]
      candidate_range: [149, 215]
      change_pct: 38.5
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 100
      candidate_median: 140
      control_range: [100, 140]
      candidate_range: [140, 200]
      change_pct: 40.0
      overlapping: true
    - metric: browser_tree_region_repaints
      control_median: 1
      candidate_median: 2
      control_range: [1, 1]
      candidate_range: [2, 2]
      change_pct: 100.0
      overlapping: false
    - metric: browser_frame_missing_px
      control_median: 269
      candidate_median: 509
      control_range: [269, 269]
      candidate_range: [509, 509]
      change_pct: 89.2
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
      Backend equivalence reports zero ordered-row and zero tally differences on an
      unchanged corpus. Every browser run passes the hard responsiveness gate without
      long tasks, network failures, rendered-preview errors, or page exceptions. The
      release predates inventory-provider diagnostics, so a measurement-only adapter
      records that missing identity instead of asserting a provider or contract the
      release did not expose.
  verdict:
    decision: rejected
    primary_metric: browser_tree_region_repaints
    reason: >-
      Every candidate profile replaces the complete Files region a second time when
      progressive discovery finishes. That doubles the measured whole-tree paints,
      grows the settled Files region from 269 to 509 pixels, duplicates mounted rows,
      and violates the release comparison rule even though backend behavior is exact
      and hard responsiveness budgets pass.
    commit: f097c667
---
# exp-027: the first v0.9.1-to-current candidate is rejected on a second root repaint

This release comparison used installed console scripts on both sides: the exact v0.9.1
tag and the wheel built from `f097c667`. Five alternating backend pairs found no
ordered-row or tally differences, and the candidate reached the first row and completed
the scan sooner while using less peak memory.

The browser result rejects that candidate.
The release painted the root tree once in all three cold profiles.
The candidate painted it twice, mounted 23 root items instead of 13, and settled the
Files region at 509 pixels instead of 269. Its terminal discovery refresh fetched an
authoritative tree after the inline baseline had already been consumed, then fell back
to replacing the whole Files region.
The refresh should reconcile the standing keyed tree in place.

Time to first byte also moved from a 12 ms median to 77 ms with non-overlapping ranges.
That does not explain the rejected layout result, but it remains a release-comparison
cost for the corrected candidate to measure and account for.
First row and first contentful paint moved nominally in the same direction, though both
ranges overlap.

The old release does not expose the inventory-provider diagnostics required by the
current recorder. As in the existing pre-contract release procedure, the baseline was
captured with the current probe and a measurement-only recorder adapter.
The resulting records preserve a null provider identity rather than pretending that
v0.9.1 reported one.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
