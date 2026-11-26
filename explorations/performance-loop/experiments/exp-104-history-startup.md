---
title: Prepare the First Commit History Page During Startup
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-104
  title: Prepare the First Commit History Page During Startup
  date: '2026-11-26'
  hypotheses:
  - H125
  subject:
    corpus: Public Metabrowser clone, commit 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, high host load
    browser: None, real loopback HTTP
  method:
    control: 5540cf06b5dc
    candidate: bfe187d4e743
    runs_per_condition: 2
    interleaved: true
    record: exp-104-history-startup.jsonl
    protocol:
      path: exp-104-protocol.txt
      sha256: a1502cff1ab9b2400d5ec236fcb257b4e0da104eb4658c8006f68d320a6883e1
  observations:
  - phase: navigation_api
    scenario: commit_history_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 366.374
  - phase: navigation_api
    scenario: commit_history_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 2
    value: 727.314
  - phase: navigation_api
    scenario: commit_history_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 1088.254
  - phase: navigation_api
    scenario: commit_history_first
    condition: baseline
    metric: server
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 363.5
  - phase: navigation_api
    scenario: commit_history_first
    condition: baseline
    metric: server
    unit: ms
    statistic: median
    sample_count: 2
    value: 723.65
  - phase: navigation_api
    scenario: commit_history_first
    condition: baseline
    metric: server
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 1083.8
  - phase: navigation_api
    scenario: commit_history_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 10.736
  - phase: navigation_api
    scenario: commit_history_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 2
    value: 10.867
  - phase: navigation_api
    scenario: commit_history_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 10.998
  - phase: navigation_api
    scenario: commit_history_first
    condition: candidate
    metric: server
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 4.6
  - phase: navigation_api
    scenario: commit_history_first
    condition: candidate
    metric: server
    unit: ms
    statistic: median
    sample_count: 2
    value: 6.6
  - phase: navigation_api
    scenario: commit_history_first
    condition: candidate
    metric: server
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 8.6
  - phase: navigation_api
    scenario: commit_history_revalidate
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 4.644
  - phase: navigation_api
    scenario: commit_history_revalidate
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 8.518
  - phase: navigation_api
    scenario: commit_history_revalidate
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 11.902
  - phase: navigation_api
    scenario: commit_history_revalidate
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 4.991
  - phase: navigation_api
    scenario: commit_history_revalidate
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 6.521
  - phase: navigation_api
    scenario: commit_history_revalidate
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 20.82
  - phase: navigation_api
    scenario: commit_history_warm
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 7.294
  - phase: navigation_api
    scenario: commit_history_warm
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 14.826
  - phase: navigation_api
    scenario: commit_history_warm
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 50.565
  - phase: navigation_api
    scenario: commit_history_warm
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 13.827
  - phase: navigation_api
    scenario: commit_history_warm
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 18.956
  - phase: navigation_api
    scenario: commit_history_warm
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 34.304
  - phase: navigation_api
    scenario: files_read_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 41.273
  - phase: navigation_api
    scenario: files_read_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 2
    value: 46.141
  - phase: navigation_api
    scenario: files_read_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 51.008
  - phase: navigation_api
    scenario: files_read_first
    condition: baseline
    metric: server
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 26.5
  - phase: navigation_api
    scenario: files_read_first
    condition: baseline
    metric: server
    unit: ms
    statistic: median
    sample_count: 2
    value: 34.15
  - phase: navigation_api
    scenario: files_read_first
    condition: baseline
    metric: server
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 41.8
  - phase: navigation_api
    scenario: files_read_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 17.151
  - phase: navigation_api
    scenario: files_read_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 2
    value: 20.349
  - phase: navigation_api
    scenario: files_read_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 23.547
  - phase: navigation_api
    scenario: files_read_first
    condition: candidate
    metric: server
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 13.7
  - phase: navigation_api
    scenario: files_read_first
    condition: candidate
    metric: server
    unit: ms
    statistic: median
    sample_count: 2
    value: 16.2
  - phase: navigation_api
    scenario: files_read_first
    condition: candidate
    metric: server
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 18.7
  - phase: navigation_api
    scenario: files_read_revalidate
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 1.882
  - phase: navigation_api
    scenario: files_read_revalidate
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 6.079
  - phase: navigation_api
    scenario: files_read_revalidate
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 9.648
  - phase: navigation_api
    scenario: files_read_revalidate
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 1.702
  - phase: navigation_api
    scenario: files_read_revalidate
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 4.616
  - phase: navigation_api
    scenario: files_read_revalidate
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 16.172
  - phase: navigation_api
    scenario: files_read_warm
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 16.027
  - phase: navigation_api
    scenario: files_read_warm
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 33.029
  - phase: navigation_api
    scenario: files_read_warm
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 80.974
  - phase: navigation_api
    scenario: files_read_warm
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 4
    value: 14.684
  - phase: navigation_api
    scenario: files_read_warm
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 4
    value: 20.741
  - phase: navigation_api
    scenario: files_read_warm
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 4
    value: 31.466
  - phase: startup
    scenario: benchmark_host
    condition: baseline
    metric: one_minute_load
    unit: count
    statistic: minimum
    sample_count: 2
    value: 256.956
  - phase: startup
    scenario: benchmark_host
    condition: baseline
    metric: one_minute_load
    unit: count
    statistic: median
    sample_count: 2
    value: 258.687
  - phase: startup
    scenario: benchmark_host
    condition: baseline
    metric: one_minute_load
    unit: count
    statistic: maximum
    sample_count: 2
    value: 260.418
  - phase: startup
    scenario: benchmark_host
    condition: candidate
    metric: one_minute_load
    unit: count
    statistic: minimum
    sample_count: 2
    value: 254.678
  - phase: startup
    scenario: benchmark_host
    condition: candidate
    metric: one_minute_load
    unit: count
    statistic: median
    sample_count: 2
    value: 255.058
  - phase: startup
    scenario: benchmark_host
    condition: candidate
    metric: one_minute_load
    unit: count
    statistic: maximum
    sample_count: 2
    value: 255.438
  - phase: startup
    scenario: commit_history
    condition: candidate
    metric: preparation
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 651.3
  - phase: startup
    scenario: commit_history
    condition: candidate
    metric: preparation
    unit: ms
    statistic: median
    sample_count: 2
    value: 660.7
  - phase: startup
    scenario: commit_history
    condition: candidate
    metric: preparation
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 670.1
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: http_ready
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 2253.563
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: http_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 3034.949
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: http_ready
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 3816.335
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: inventory_ready
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 2858.642
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: inventory_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 3805.036
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: inventory_ready
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 4751.431
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: server_rss_at_inventory_ready
    unit: bytes
    statistic: minimum
    sample_count: 2
    value: 93405184
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: server_rss_at_inventory_ready
    unit: bytes
    statistic: median
    sample_count: 2
    value: 93560832.0
  - phase: startup
    scenario: fresh_server
    condition: baseline
    metric: server_rss_at_inventory_ready
    unit: bytes
    statistic: maximum
    sample_count: 2
    value: 93716480
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: http_ready
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 3507.414
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: http_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 5133.61
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: http_ready
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 6759.807
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: inventory_ready
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 4245.653
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: inventory_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 5858.32
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: inventory_ready
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 7470.987
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: server_rss_at_inventory_ready
    unit: bytes
    statistic: minimum
    sample_count: 2
    value: 91521024
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: server_rss_at_inventory_ready
    unit: bytes
    statistic: median
    sample_count: 2
    value: 92528640.0
  - phase: startup
    scenario: fresh_server
    condition: candidate
    metric: server_rss_at_inventory_ready
    unit: bytes
    statistic: maximum
    sample_count: 2
    value: 93536256
  annotations:
  - kind: change
    text: The server prepares the normal first history page once, using the same registry
      and ref state as the reader.
  - kind: finding
    text: With matching dependencies, first history HTTP requests took 366–1,088 ms
      on control and about 10 ms on candidate. Candidate preparation took 651–670
      ms.
  - kind: limitation
    text: Only two fresh starts per condition on a busy host. Startup readiness varied,
      and first useful browser paint needs a separate run.
  - kind: limitation
    text: An initial series with different build-only packages was retained as a pilot
      and excluded from the reported numbers.
  verdict:
    decision: diagnostic
    primary_metric: first Commits history HTTP read after startup
    reason: The real HTTP read and shared-walk checks support the hypothesis. Host
      load and limited sample count leave the startup and paint acceptance gates open.
---
# Exp-104: Prepare the First Commit History Page During Startup

The first history read fell from 366–1,088 ms on the control to about 10 ms on the
candidate in four interleaved starts.
The two candidate servers finished the history job in 651–670 ms.
Both completed preparation before the first history request.
Response fields, checked content hashes, and ETag semantics matched between builds.

First Files reads took 41–51 ms on the control and 17–23 ms on the candidate.
Inventory readiness varied from 2.86–4.75 s on the control and 4.25–7.47 s on the
candidate. The host load was above the benchmark guard for every start.
These samples leave the startup cost and browser acceptance unresolved.
The registry tests cover reuse when the first reader overlaps preparation and refusal to
start a walk with no reuse key.

The [protocol](exp-104-protocol.txt) and [samples](exp-104-history-startup.jsonl) record
the measurement and its limits.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
