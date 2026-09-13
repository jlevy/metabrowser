---
title: The final v0.9.2 candidate bounds 300k catalog delivery
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-032
  title: The final v0.9.2 candidate bounds 300k catalog delivery
  date: "2026-09-11"
  hypotheses: []
  subject:
    corpus: fingerprinted synthetic tree tree-3a5e80fa
    corpus_files: 300000
    corpus_dirs: 1105
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: exact installed v0.9.1 wheel built from tag commit 16211ccb
    candidate: exact installed wheel built from 863dcd9c
    record: >-
      runs.jsonl labels exp-032-release-v091-final and exp-032-candidate-863dcd9c-final,
      captured with harness 21 in one standard CPython 3.14.7 environment that alternated
      only the Metabrowser wheel; plus five backend runs per side from compare_builds
  results:
    - metric: backend_spawn_to_serving_s
      control_median: 0.679
      candidate_median: 0.787
      control_range: [0.646, 1.984]
      candidate_range: [0.719, 0.841]
      change_pct: 15.9
      overlapping: true
    - metric: backend_first_row_s
      control_median: 0.799
      candidate_median: 0.529
      control_range: [0.536, 0.809]
      candidate_range: [0.486, 0.785]
      change_pct: -33.8
      overlapping: true
    - metric: backend_index_done_s
      control_median: 11.698
      candidate_median: 11.91
      control_range: [11.136, 13.38]
      candidate_range: [11.797, 12.263]
      change_pct: 1.8
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 306.8
      candidate_median: 316.8
      control_range: [304.2, 314.7]
      candidate_range: [314.9, 316.8]
      change_pct: 3.3
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 111
      candidate_median: 122
      control_range: [107, 140]
      candidate_range: [103, 161]
      change_pct: 9.9
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 100
      candidate_median: 100
      control_range: [96, 108]
      candidate_range: [100, 116]
      change_pct: 0.0
      overlapping: true
    - metric: browser_tree_fetch_srv_ms
      control_median: 3
      candidate_median: 14
      control_range: [3, 4]
      candidate_range: [11, 17]
      change_pct: 366.7
      overlapping: false
    - metric: browser_long_tasks
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      change_pct: 0.0
      overlapping: true
    - metric: browser_inventory_delivery_batch_items_max
      control_median: 17787
      candidate_median: 4096
      control_range: [16068, 26265]
      candidate_range: [4096, 4096]
      change_pct: -77.0
      overlapping: false
    - metric: browser_inventory_delivery_max_ms
      control_median: 5
      candidate_median: 6
      control_range: [5, 6]
      candidate_range: [5, 10]
      change_pct: 20.0
      overlapping: true
    - metric: browser_inventory_delivery_work_ms_total
      control_median: 190
      candidate_median: 259
      control_range: [185, 209]
      candidate_range: [250, 262]
      change_pct: 36.3
      overlapping: false
    - metric: browser_inventory_delivery_work_pct
      control_median: 1.3
      candidate_median: 1.4
      control_range: [1, 1.4]
      candidate_range: [1.3, 1.4]
      change_pct: 7.7
      overlapping: true
    - metric: browser_inventory_delivery_attribution_missing
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: browser_js_heap_mb
      control_median: 45
      candidate_median: 55.6
      control_range: [42.7, 45.2]
      candidate_range: [55.2, 73.8]
      change_pct: 23.6
      overlapping: false
    - metric: browser_js_heap_after_gc_mb
      control_median: 38.5
      candidate_median: 38.9
      control_range: [38.3, 38.5]
      candidate_range: [38.8, 38.9]
      change_pct: 1.0
      overlapping: false
    - metric: browser_walk_elapsed_ms
      control_median: 12770
      candidate_median: 16767
      control_range: [12661, 20341]
      candidate_range: [16600, 18140]
      change_pct: 31.3
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
  complexity:
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      The backend comparison ran against the 4fe3dfae wheel. Commit 863dcd9c changes only
      the performance harness and its tests, so the shipped sources are identical. Walk
      times for v0.9.1 come from its server logs, because that release's log line predates
      the provider-qualified format the recorder parses.
  verdict:
    decision: accepted
    primary_metric: browser_inventory_delivery_batch_items_max
    reason: >-
      Every candidate profile passes the hard responsiveness gate with complete delivery
      attribution, no Long Tasks, a complete catalog, and catalog batches held at 4,096
      items. Backend rows and tallies match v0.9.1 exactly. The repeatable wrong-way
      results are small and inside budget: root tree fetch server time, transient JS heap,
      total delivery work spread across smaller batches, and about 10 MiB of backend RSS.
      Walk completion with a browser attached is unresolved and tracked separately; it is
      equal in the paired series and slower in this one, with identical shipped sources.
    commit: 863dcd9c
---
# exp-032: the final v0.9.2 candidate bounds 300k catalog delivery

This is the release comparison for the post-#108 hardening branch, on a 300,000-file
corpus instead of exp-031’s 60,000. Only the final pair of labels is admissible
evidence; the earlier exp-032 labels in the ledger are retained diagnostics.

- `exp-032-candidate-feda3db8` (one run) failed the 5% delivery-work gate at 8.7%. The
  cause was a second client pass over one settled 300k catalog payload, fixed in
  `4fe3dfae`.
- `exp-032-candidate-4fe3dfae` and `exp-032-release-v091` passed the candidate’s hard
  gates but used two virtual environments whose installed-record hashes differed, so the
  comparison refused them.
- The `-paired` labels used one environment and passed, but the control label holds six
  rows for five executions after a failed automation retry.
  Commit `863dcd9c` makes `record` refuse a reused nonce, and the final series was
  captured under that harness.

## Result

All five candidate profiles pass every hard budget.
Catalog delivery is fully attributed, with no batch above 4,096 items; v0.9.1 delivers
16,068–26,265 items at once and leaves one delivery callback unattributed per run.
Neither condition shows a Long Task in this series.
The v0.9.1 paired series did show them, at 119–168 ms, when its catalog arrived as one
300,000-item batch, so the control’s behavior depends on scan timing while the
candidate’s bound does not.

FCP and first-row ranges overlap, and the tree region paints once in both conditions.
The backend comparison finds no row or tally difference.
Its first-row median improves from 0.799 s to 0.529 s, with overlapping ranges.

## Wrong-way results

These repeat across all five runs, and none approaches a hard budget:

- Root `/api/tree` server time rises from 3 ms to 14 ms, and `load_tree_ms` from 7 ms to
  17 ms.
- Total delivery work rises from 190 ms to 259 ms because the same items arrive in about
  1,333 bounded batches instead of about 1,227 larger ones.
- Peak JS heap rises from 45 MB to 56 MB; after garbage collection the difference is 0.4
  MB, so this is transient allocation, not retained state.
- Backend peak RSS is about 10 MiB higher, at 316.8 MiB against 306.8 MiB.
- Backend spawn-to-serving rises from a 0.679 s to a 0.787 s median, and the whole
  candidate range sits above the control median.
  That fits `metab serve` importing KPress and resolving the shell’s KPress assets
  before Uvicorn starts, which moves that cost out of the first render-blocking
  stylesheet request.

## Scope of this evidence

This record measures the wheel built from `863dcd9c`. Release review afterwards changed
shipped browser and server sources (catalog removal and compaction, Markdown literal
masking and in-document navigation, resync handling, and KPress request validation), so
it does not describe the final artifact.
The quiet-machine rerun tracked in `mb-afdb` must measure the final release commit.

## Unresolved: walk completion with a browser attached

The candidate’s walk took 16.6–18.1 s in this series, while v0.9.1 took 12.7–13.0 s in
four runs and 20.3 s in one.
The same shipped sources walked in 11.0–12.3 s in the paired series, where v0.9.1 took
11.1–11.8 s, and the backend-only comparison, with no browser attached, shows
overlapping index-completion ranges.
The slowdown is therefore neither consistent nor attributable from this evidence.
It needs a quiet, dedicated measurement of server-side work during an active walk with a
connected browser before any claim is made in either direction.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
