---
title: Fetch Exact Changes Commits Before the Full Origin
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-113
  title: Fetch Exact Changes Commits Before the Full Origin
  date: '2026-11-26'
  hypotheses:
  - H127
  - H132
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 with recorded Changes commits
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, public Git HTTPS with the application repository store policy
  method:
    control: Wide-first transport at 69042dc6daec
    candidate: Exact-first transport at 69042dc6daec
    record: exp-113-origin-fetch-order.jsonl
    interleaved: true
    runs_per_condition: 2
    protocol:
      path: exp-113-protocol.txt
      sha256: 3e6adaffe814ce2f3d51b8dab371e799e4b447a2c80c3e03f56fec6b7bc62fba
  observations:
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: wide_first
    metric: time_to_exact_ms
    unit: ms
    statistic: median
    sample_count: 2
    value: 17331.4
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: wide_first
    metric: total_ms
    unit: ms
    statistic: median
    sample_count: 2
    value: 17907.35
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: wide_first
    metric: bytes_held
    unit: bytes
    statistic: median
    sample_count: 2
    value: 68255499.5
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: wide_first
    metric: origin_ref_count
    unit: count
    statistic: median
    sample_count: 2
    value: 178.0
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: time_to_exact_ms
    unit: ms
    statistic: median
    sample_count: 2
    value: 10238.85
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: total_ms
    unit: ms
    statistic: median
    sample_count: 2
    value: 19245.3
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: bytes_held
    unit: bytes
    statistic: median
    sample_count: 2
    value: 89684793.0
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: origin_ref_count
    unit: count
    statistic: median
    sample_count: 2
    value: 178.0
  annotations:
  - kind: finding
    text: Exact-first produced the same checked diff and final ref digest with approximately 89.7
      MB held versus 68.2 MB wide-first.
  - kind: finding
    text: The exact comparison became readable in 9.46 and 11.02 seconds exact-first versus 11.99
      and 22.67 seconds wide-first.
  - kind: limitation
    text: Total times overlapped. Transport ordering by itself cannot make the product serve a comparison
      from a staging store.
  verdict:
    decision: diagnostic
    primary_metric: first readable exact Changes comparison
    reason: Both pairs reached the exact commits sooner, with a measurable extra bytes cost and two
      runs per condition.
---
# Exp-113: Fetch Exact Changes Commits Before the Full Origin

Fetching the observed base and public pull head first made the comparison readable in
9.46 and 11.02 s. The existing wide fetch made it readable in 11.99 and 22.67 s. Both
conditions returned the same binary diff digest and the same set of 178 origin refs.
The exact-first stores retained about 89.7 MB, compared with about 68.2 MB for
wide-first. Times to finish both fetches overlapped.

Each isolated run used the same admitted checkout as an object lender.
It finished both fetches and checked the exact diff and public refs.
Two earlier attempts were refused because the probe had supplied incomplete policy flags
for reading a store.
The retained measurements use the application’s own store diff wrapper.

The [protocol](exp-113-protocol.txt) and [samples](exp-113-origin-fetch-order.jsonl)
scope the findings to transport order.
Serving a comparison before the full store exists would require a separate publication
and ownership design.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
