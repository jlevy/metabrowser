---
title: The cold-shell fix is rejected on a catalog-completion gap
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-029
  title: The cold-shell fix is rejected on a catalog-completion gap
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
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.9.1 release built from tag commit 16211ccb
    candidate: exact installed wheel from 29ee1776
    record: five backend pairs; browser round stopped after one control and two candidate profiles
  results:
    - metric: backend_first_row_s
      control_median: 0.323
      candidate_median: 0.056
      control_range: [0.101, 0.340]
      candidate_range: [0.023, 0.110]
      change_pct: -82.7
      overlapping: true
    - metric: backend_index_done_s
      control_median: 5.378
      candidate_median: 6.058
      control_range: [4.413, 5.935]
      candidate_range: [3.320, 6.192]
      change_pct: 12.6
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 120.2
      candidate_median: 114.4
      control_range: [118.5, 120.9]
      candidate_range: [113.7, 122.2]
      change_pct: -4.8
      overlapping: true
    - metric: backend_tally_overlap_progress_max_ms
      control_median: 75.4
      candidate_median: 96.6
      control_range: [65.2, 151.2]
      candidate_range: [78.0, 170.5]
      change_pct: 28.1
      overlapping: true
    - metric: browser_ttfb_ms
      control_median: 12
      candidate_median: 27
      control_range: [12, 12]
      candidate_range: [27, 27]
      change_pct: 125.0
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
      candidate_median: 0.5
      control_range: [0, 0]
      candidate_range: [0, 1]
      overlapping: true
    - metric: browser_hard_gate_pass_rate_pct
      control_median: 100
      candidate_median: 50
      control_range: [100, 100]
      candidate_range: [0, 100]
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      Backend equivalence reports zero ordered-row and zero tally differences on an
      unchanged corpus. Both candidate browser profiles preserve the same one-paint tree and
      269-pixel Files-region result as the release, with no long tasks, network failures,
      rendered-preview errors, or page exceptions. One earlier candidate capture failed
      only the trusted-input coverage rule floor and was not recorded.
  verdict:
    decision: rejected
    primary_metric: browser_file_catalog_incomplete
    reason: >-
      Two bounded event-stream queue overflows correctly requested fresh snapshots, but
      the second reconnect backoff crossed scan completion. The server progress endpoint
      reported done while the browser's Quick File catalog remained incomplete because
      its terminal capability event could not reach the detached stream. The existing
      lightweight progress poll must provide an independent, coalesced completion signal.
    commit: 29ee1776
---
# exp-029: the cold-shell fix is rejected on a catalog-completion gap

The cold-shell change did what exp-028 asked of it: the two recorded candidate profiles
both reached a 27 ms time to first byte instead of that round’s 66–69 ms range.
The tree also retained one whole-region paint, 13 mounted root items, and the release’s
269-pixel Files-region result.
This round stopped before the planned three balanced pairs, so its browser timings are
diagnostic rather than a release claim.

The second candidate profile failed a correctness gate.
The server log records two bounded event-stream queue overflows while the 60,000-file
walk was active. Each overflow correctly replaced the connection with a resynchronizing
snapshot, but the second reconnect used a four-second backoff.
The scan finished during that interval, after the catalog’s immediate resync fetch had
returned a partial prefix and while no stream was attached to receive the terminal
capability event. The browser therefore reported a settled index and an incomplete Quick
File catalog.

The shell already polls the lightweight `/api/index/progress` route while discovery is
active. That route observed the same terminal state independently and is the right
fallback when the stream carrying the normal completion notification is between
connections. The follow-up wires that terminal poll to the catalog feed and coalesces it
with the normal stream signal so one continuity gap performs one authoritative refetch.
The feed behavior is pinned in the dependency-free Node contract suite; this is browser
coordination behavior, while the underlying route, model, and catalog data remain in the
CLI and Python test surfaces.

Five installed-console-script backend pairs still returned identical ordered rows and
tallies on an unchanged 60,002-file physical fingerprint.
Every timing and memory range overlaps except the earlier first-row delivery, so no
backend regression is inferred.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
