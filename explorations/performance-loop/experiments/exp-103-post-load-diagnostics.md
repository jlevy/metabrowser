---
title: Post-Load Navigation and Preparation Diagnostics
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-103
  title: Post-Load Navigation and Preparation Diagnostics
  date: '2026-11-26'
  hypotheses:
  - H88
  - H104
  - H106
  - H114
  - H117
  subject:
    corpus: Public Metabrowser clone, commit 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, high host load
    browser: Headless Chrome 152 and browser-free HTTP/provider probes
    viewport: 1440x900 for transitions
  method:
    record: exp-103-observations.jsonl
    protocol:
      path: exp-103-protocol.txt
      sha256: ec8461ca5f37acb81125bc0dcf1d399da4a56f3078caf8bd60f9f75686161f64
  observations:
  - phase: startup
    scenario: http_server
    condition: fresh
    metric: inventory_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 4806.62
  - phase: navigation_api
    scenario: history
    condition: fresh_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 478.97
  - phase: navigation_api
    scenario: history
    condition: fresh_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 474.9
  - phase: navigation_api
    scenario: detail
    condition: fresh_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 79.91
  - phase: navigation_api
    scenario: detail
    condition: fresh_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 56.8
  - phase: navigation_api
    scenario: comparison
    condition: fresh_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 211.73
  - phase: navigation_api
    scenario: comparison
    condition: fresh_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 205.3
  - phase: navigation_api
    scenario: large_file
    condition: fresh_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 31.32
  - phase: navigation_api
    scenario: large_file
    condition: fresh_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 22
  - phase: navigation_api
    scenario: history
    condition: fresh_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 20.91
  - phase: navigation_api
    scenario: history
    condition: fresh_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 8.9
  - phase: navigation_api
    scenario: detail
    condition: fresh_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 41.9
  - phase: navigation_api
    scenario: detail
    condition: fresh_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 38.1
  - phase: navigation_api
    scenario: comparison
    condition: fresh_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 76
  - phase: navigation_api
    scenario: comparison
    condition: fresh_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 69
  - phase: navigation_api
    scenario: large_file
    condition: fresh_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 43.81
  - phase: navigation_api
    scenario: large_file
    condition: fresh_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 35.6
  - phase: startup
    scenario: http_server
    condition: prepared
    metric: inventory_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 4936.58
  - phase: startup
    scenario: http_server
    condition: prepared
    metric: startup_preparation
    unit: ms
    statistic: sample
    sample_count: 1
    value: 1019.3
  - phase: navigation_api
    scenario: history
    condition: prepared_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 17.3
  - phase: navigation_api
    scenario: history
    condition: prepared_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 14.9
  - phase: navigation_api
    scenario: detail
    condition: prepared_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 60.76
  - phase: navigation_api
    scenario: detail
    condition: prepared_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 52.3
  - phase: navigation_api
    scenario: comparison
    condition: prepared_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 83.51
  - phase: navigation_api
    scenario: comparison
    condition: prepared_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 81.3
  - phase: navigation_api
    scenario: large_file
    condition: prepared_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 23.63
  - phase: navigation_api
    scenario: large_file
    condition: prepared_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 21.8
  - phase: navigation_api
    scenario: history
    condition: prepared_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 11.31
  - phase: navigation_api
    scenario: history
    condition: prepared_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 9
  - phase: navigation_api
    scenario: detail
    condition: prepared_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 28.24
  - phase: navigation_api
    scenario: detail
    condition: prepared_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 26.5
  - phase: navigation_api
    scenario: comparison
    condition: prepared_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 64.6
  - phase: navigation_api
    scenario: comparison
    condition: prepared_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 62.6
  - phase: navigation_api
    scenario: large_file
    condition: prepared_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 14.59
  - phase: navigation_api
    scenario: large_file
    condition: prepared_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 12.5
  - phase: startup
    scenario: http_server
    condition: seeded_pr
    metric: inventory_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 10152.79
  - phase: navigation_api
    scenario: pull_record
    condition: seeded_pr_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 435.56
  - phase: navigation_api
    scenario: pull_record
    condition: seeded_pr_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 406.9
  - phase: navigation_api
    scenario: pull_body
    condition: seeded_pr_first
    metric: request_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 2084.83
  - phase: navigation_api
    scenario: pull_body
    condition: seeded_pr_first
    metric: server_work
    unit: ms
    statistic: sample
    sample_count: 1
    value: 2077.5
  - phase: navigation_api
    scenario: pull_record
    condition: seeded_pr_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 31.88
  - phase: navigation_api
    scenario: pull_record
    condition: seeded_pr_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 21.7
  - phase: navigation_api
    scenario: pull_body
    condition: seeded_pr_warm
    metric: request_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 19.52
  - phase: navigation_api
    scenario: pull_body
    condition: seeded_pr_warm
    metric: server_work
    unit: ms
    statistic: median
    sample_count: 3
    value: 9.2
  - phase: browser_navigation
    scenario: files.cold.image
    condition: original_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 180.5
  - phase: browser_navigation
    scenario: files.cold.image
    condition: original_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 5
  - phase: browser_navigation
    scenario: files.cold.image
    condition: original_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: files.cold.markdown_large
    condition: original_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 5652.3
  - phase: browser_navigation
    scenario: files.cold.markdown_large
    condition: original_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: files.cold.markdown_large
    condition: original_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: fresh_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 18928.6
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: fresh_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 8
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: fresh_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 1082
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: fresh_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 5197.3
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: fresh_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: fresh_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 292
  - phase: browser_navigation
    scenario: pulls.tab.checks_first
    condition: fresh_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 38.7
  - phase: browser_navigation
    scenario: pulls.tab.checks_first
    condition: fresh_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.checks_first
    condition: fresh_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.conversation_revisit
    condition: fresh_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 46.9
  - phase: browser_navigation
    scenario: pulls.tab.conversation_revisit
    condition: fresh_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.conversation_revisit
    condition: fresh_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: fresh_refused
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 356.7
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: fresh_refused
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: fresh_refused
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 8
  - phase: browser_navigation
    scenario: files.cold.image
    condition: fresh_image_candidate
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 564.1
  - phase: browser_navigation
    scenario: files.cold.image
    condition: fresh_image_candidate
    metric: blank_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 1
  - phase: browser_navigation
    scenario: files.cold.image
    condition: fresh_image_candidate
    metric: placeholder_frames
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: startup
    scenario: files_landing
    condition: fresh_refused
    metric: useful_landing_observed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 4204.9
  - phase: startup
    scenario: files_landing
    condition: fresh_refused
    metric: browsing_setup_started
    unit: ms
    statistic: sample
    sample_count: 1
    value: 6734.2
  - phase: provider
    scenario: first_pr
    condition: fresh_refused
    metric: overlapping_gh_calls
    unit: requests
    statistic: sample
    sample_count: 1
    value: 20
  - phase: provider
    scenario: first_pr
    condition: fresh_refused
    metric: peak_overlapping_gh
    unit: processes
    statistic: sample
    sample_count: 1
    value: 5
  - phase: provider
    scenario: first_pr
    condition: fresh_refused
    metric: checkout_fetch_elapsed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 31588.9
  - phase: provider
    scenario: two_rest_reads
    condition: serial
    metric: batch_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 2054.44
  - phase: provider
    scenario: two_rest_reads
    condition: parallel
    metric: batch_elapsed
    unit: ms
    statistic: median
    sample_count: 3
    value: 1518.83
  - phase: provider
    scenario: conditional_rest
    condition: live
    metric: response_bytes
    unit: bytes
    statistic: median
    sample_count: 3
    value: 0
  - phase: provider
    scenario: two_subject_graphql_projection
    condition: live
    metric: cost
    unit: points
    statistic: median
    sample_count: 3
    value: 1
  - phase: browser_rendering
    scenario: diff-layout
    condition: static_fixture
    metric: mount
    unit: ms
    statistic: sample
    sample_count: 1
    value: 35.5
  - phase: browser_rendering
    scenario: diff-layout
    condition: static_fixture
    metric: layout_switch_blocking
    unit: ms
    statistic: median
    sample_count: 6
    value: 26.45
  - phase: browser_rendering
    scenario: diff-intraline:ordinary code
    condition: static_fixture
    metric: refinement
    unit: ms
    statistic: sample
    sample_count: 1
    value: 2.2
  - phase: browser_rendering
    scenario: diff-intraline:shifted unequal lines
    condition: static_fixture
    metric: refinement
    unit: ms
    statistic: sample
    sample_count: 1
    value: 0.3
  - phase: browser_rendering
    scenario: diff-intraline:minified similar long line
    condition: static_fixture
    metric: refinement
    unit: ms
    statistic: sample
    sample_count: 1
    value: 2.9
  - phase: browser_rendering
    scenario: diff-intraline:unrelated long lines
    condition: static_fixture
    metric: refinement
    unit: ms
    statistic: sample
    sample_count: 1
    value: 34.5
  - phase: browser_rendering
    scenario: diff-intraline:8 MiB patch-bound similar line
    condition: static_fixture
    metric: refinement
    unit: ms
    statistic: sample
    sample_count: 1
    value: 25
  - phase: browser_rendering
    scenario: diff-intraline:8 MiB patch-bound unrelated lines
    condition: static_fixture
    metric: refinement
    unit: ms
    statistic: sample
    sample_count: 1
    value: 37.9
  annotations:
  - kind: change
    text: The image renderer reports decode readiness to the preview compositor.
  - kind: finding
    text: Preparing history and comparison moved work into the explicitly timed startup preparation
      phase.
  - kind: finding
    text: The selected PR's first gh call began shortly after checkout acquisition finished.
  - kind: limitation
    text: High host load and the refused Pulls journey preclude an acceptance comparison.
  - kind: limitation
    text: HTTP, renderer, and provider observations measure separate workloads.
  verdict:
    decision: diagnostic
    primary_metric: first useful destination after startup
    reason: One-off wiring and attribution measurements with varied cache regimes and no eligible
      control/candidate series.
---
# Exp-103: Post-Load Navigation and Preparation Diagnostics

These observations accompany the
[post-load survey](../../../docs/project/research/research-2026-11-26-post-load-performance.md).
The [protocol](exp-103-protocol.txt) records the regimes and the
[samples](exp-103-observations.jsonl) retain their measured values.
The experiment’s verdict records its diagnostic status for later charting.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
