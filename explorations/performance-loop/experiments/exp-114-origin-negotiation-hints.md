---
title: Negotiate the Broad Fetch With the Exact Commits Already Obtained
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-114
  title: Negotiate the Broad Fetch With the Exact Commits Already Obtained
  date: '2026-11-26'
  hypotheses:
  - H133
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 with recorded Changes commits
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, public Git HTTPS with the application repository store policy
  method:
    control: Exact-first ordinary hints at 69042dc6daec
    candidate: Exact-first plus its base and head as broad fetch hints at 69042dc6daec
    record: exp-114-origin-negotiation-hints.jsonl
    protocol:
      path: exp-114-protocol.txt
      sha256: 1b3dac9e29fe2720a4d2cf88911a6ebb7d1e0497cf2997c7bd241fb9c80a6789
  observations:
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: time_to_exact_ms
    unit: ms
    statistic: sample
    sample_count: 1
    value: 16438.6
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: total_ms
    unit: ms
    statistic: sample
    sample_count: 1
    value: 27926.5
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: bytes_held
    unit: bytes
    statistic: sample
    sample_count: 1
    value: 90061521
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first
    metric: origin_ref_count
    unit: count
    statistic: sample
    sample_count: 1
    value: 178
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first_with_new_tips
    metric: time_to_exact_ms
    unit: ms
    statistic: median
    sample_count: 2
    value: 20626.8
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first_with_new_tips
    metric: total_ms
    unit: ms
    statistic: median
    sample_count: 2
    value: 28099.65
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first_with_new_tips
    metric: bytes_held
    unit: bytes
    statistic: median
    sample_count: 2
    value: 76221872.0
  - phase: provider
    scenario: exact_changes_origin_transport
    condition: exact_first_with_new_tips
    metric: origin_ref_count
    unit: count
    statistic: median
    sample_count: 2
    value: 178.0
  annotations:
  - kind: finding
    text: The matching-ref control retained 90.1 MB and both hinted stores retained 76.2 MB. The
      final diff and ref digests match.
  - kind: limitation
    text: The origin refs changed from exp-113. One new control restored the exact ref comparison.
      Total times still overlapped.
  verdict:
    decision: diagnostic
    primary_metric: overlay bytes after exact and wildcard fetches
    reason: Two hinted samples used fewer bytes than the same-ref control. No production scheduling
      or wall-clock verdict follows.
---
# Exp-114: Negotiate the Broad Fetch With the Exact Commits Already Obtained

Passing the fetched base and head as negotiation tips for the following wildcard fetch
kept about 76.2 MB on disk in each run.
The exact-first control with ordinary hints kept 90.1 MB. The three runs produced the
same 178-ref digest and the same binary diff digest.
Their total times overlapped.

The public origin changed between exp-113 and this run.
A fresh exact-first control after the two candidate runs matched the new ref digest.
The result uses that control.
The earlier ordinary runs remain in the sample record with their different origin digest
and do not count in the byte comparison.

The [protocol](exp-114-protocol.txt) and
[samples](exp-114-origin-negotiation-hints.jsonl) support a transport follow-up.
The product still needs an isolated way to serve verified Changes content during origin
acquisition.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
