---
title: The repainted-tree fix is rejected on an avoidable cold shell import
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-028
  title: The repainted-tree fix is rejected on an avoidable cold shell import
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
    candidate: exact installed wheel from ec45e186
    record: five backend pairs and three admissible browser profiles per exact build
  results:
    - metric: backend_first_row_s
      control_median: 0.270
      candidate_median: 0.011
      control_range: [0.009, 0.277]
      candidate_range: [0.010, 0.012]
      change_pct: -95.9
      overlapping: true
    - metric: backend_index_done_s
      control_median: 1.335
      candidate_median: 1.326
      control_range: [1.321, 1.599]
      candidate_range: [1.085, 1.334]
      change_pct: -0.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 119.7
      candidate_median: 114.2
      control_range: [118.1, 121.3]
      candidate_range: [113.9, 120.7]
      change_pct: -4.6
      overlapping: true
    - metric: backend_tally_while_progressing_ms
      control_median: 330.2
      candidate_median: 353.2
      control_range: [327.9, 346.0]
      candidate_range: [346.5, 361.7]
      change_pct: 7.0
      overlapping: false
    - metric: browser_ttfb_ms
      control_median: 12
      candidate_median: 67
      control_range: [11, 14]
      candidate_range: [66, 69]
      change_pct: 458.3
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 113
      candidate_median: 123
      control_range: [111, 136]
      candidate_range: [121, 137]
      change_pct: 8.8
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 116
      candidate_median: 132
      control_range: [108, 144]
      candidate_range: [124, 136]
      change_pct: 13.8
      overlapping: true
    - metric: browser_subtree_requests
      control_median: 13
      candidate_median: 16
      control_range: [13, 13]
      candidate_range: [16, 16]
      change_pct: 23.1
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
      unchanged corpus. The keyed completion refresh restores one whole-tree paint,
      the release's 269-pixel Files-region result, and 13 mounted root items. All six
      accepted browser profiles have no long tasks, network failures, rendered-preview
      errors, or page exceptions. The server-tally comparison is 23 ms slower under
      synthetic contention, while overall scan completion ranges overlap and backend
      first-row delivery is substantially earlier.
  verdict:
    decision: rejected
    primary_metric: browser_ttfb_ms
    reason: >-
      The visual regression is fixed, but every admissible candidate profile pays a
      repeatable 55 ms cold-shell delay. Direct attribution finds 98 ms of a 120 ms
      first shell render importing the KPress renderer only to construct two versioned
      font URLs. The same URLs can be constructed from locked distribution metadata in
      a 22 ms shell render without weakening the CLI's lazy dependency boundary.
    commit: ec45e186
---
# exp-028: the repainted-tree fix is rejected on an avoidable cold shell import

The candidate fixes the release blocker from exp-027. Three admissible profiles paint
the root tree once, mount the same 13 items as v0.9.1, and leave the same 269 pixels
below the shipped Files skeleton.
Every hard responsiveness and correctness gate passes, and five backend pairs return
identical ordered rows and tallies from an unchanged corpus.

It is still not the final candidate.
Time to first byte moves from 12 ms to 67 ms on non-overlapping ranges.
Six additional candidate captures missed the predetermined 80% trusted-input coverage
floor and were therefore not recorded as condition evidence; their TTFB ranged from 96
ms to 1,050 ms. The evidence rule excludes them from the comparison, but their existence
made the cold critical path worth attributing rather than retrying until it looked
quiet.

An instrumented first render inside the exact installed candidate attributes 97.8 ms of
its 120.2 ms total to the first `kpress_static_url` call.
That call imports the whole document-rendering runtime to build two strings: the
versioned Source Sans font and style-token URLs in the shell.
Constructing the same public URL shape from the locked KPress distribution version
leaves a 22.1 ms shell render in the same diagnostic.
This is a narrow host-adapter fix; eager KPress import would merely move the cost
earlier and would regress CLI and API-only commands.

The backend contention probe also records a smaller, repeatable cost: the candidate’s
tally request is 23 ms slower and its progress-poll maximum is higher, while overall
scan completion overlaps.
Browser first-row and paint ranges overlap, all interaction latencies stay below the
hard budget, and no main-thread blocking appears.
Those facts are retained rather than turned into a speed claim.

One earlier `394abb2c` profile remains in the append-only ledger under its own label.
It identified that real-tree runs discarded the supplied file count and relied on a slow
scan’s INFO log for provenance.
The harness now retains the explicit count and falls back to `/api/index/progress` when
a fast scan correctly logs completion only at DEBUG; that intermediate label is not part
of this comparison.

The v0.9.1 control predates provider diagnostics.
Its profiles use the established measurement-only recorder adapter, retain a null
provider identity, and are validated against the current evidence and budget policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
