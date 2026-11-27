---
title: Focused HTTP Loop for Named API Cases
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-106
  title: Focused HTTP Loop for Named API Cases
  date: '2026-11-26'
  hypotheses:
  - H129
  subject:
    corpus: Public Metabrowser clone, commit 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, real loopback HTTP
  method:
    record: exp-106-focused-http-loop.jsonl
    protocol:
      path: exp-106-protocol.txt
      sha256: 119efa288d2f4df0f6a21ba0833407cb2cfb1ef0b884f131f91febb822d569bc
  observations:
  - phase: navigation_api
    scenario: diagnostic_driver
    condition: wide
    metric: recorded_requests
    unit: requests
    statistic: sample
    sample_count: 1
    value: 22
  - phase: navigation_api
    scenario: diagnostic_driver
    condition: wide
    metric: harness_invocation
    unit: ms
    statistic: sample
    sample_count: 1
    value: 20000
  - phase: navigation_api
    scenario: diagnostic_driver
    condition: focused
    metric: recorded_requests
    unit: requests
    statistic: sample
    sample_count: 1
    value: 3
  - phase: navigation_api
    scenario: diagnostic_driver
    condition: focused
    metric: harness_invocation
    unit: ms
    statistic: sample
    sample_count: 1
    value: 12000
  annotations:
  - kind: change
    text: Time only the named API cases after HTTP and inventory readiness.
  - kind: finding
    text: The wide invocation recorded 22 requests and the focused invocation recorded
      three, with the same checked history hash and HTTP 304.
  - kind: limitation
    text: One invocation per workload. Elapsed includes setup and varying host load
      and is a tooling diagnostic only.
  verdict:
    decision: diagnostic
    primary_metric: requests recorded for the short API iteration
    reason: The driver omitted unrelated workloads while preserving the checked response
      contract.
---
# Exp-106: Focused HTTP Loop for Named API Cases

The wide loop recorded 22 requests.
The focused loop recorded the three requested history reads: first, repeated, and
conditional. They agreed on the checked first-page hash and conditional 304. The two
invocations took 20 and 12 seconds on a busy Mac, with different amounts of work.
Keep the wide run for inventory and Files guards.

The [protocol](exp-106-protocol.txt) and [observations](exp-106-focused-http-loop.jsonl)
capture the comparison.
The [short-round runbook](../README.md#short-http-rounds) explains when to use it.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
