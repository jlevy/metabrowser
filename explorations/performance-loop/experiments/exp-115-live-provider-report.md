---
title: Verify the GitHub Request Report Through the Live Server
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-115
  title: Verify the GitHub Request Report Through the Live Server
  date: '2026-11-26'
  hypotheses:
  - H128
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 and public pull request 888
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, actual loopback HTTP server and live GitHub
  method:
    candidate: 55bb41ddc
    record: exp-115-live-provider-report.jsonl
    protocol:
      path: exp-115-protocol.txt
      sha256: bc2b4d82175b96168d8540afb1618cc5fa5394df4d70bb451e67d893c4a5f7dc
  observations:
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: gh_processes
    unit: processes
    value: 7
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: gh_peak_in_flight
    unit: processes
    value: 3
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: rest_processes
    unit: processes
    value: 6
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: rest_core_charged
    unit: requests
    value: 5
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: graphql_points
    unit: points
    value: 1
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: not_modified
    unit: requests
    value: 1
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: slot_queue_total
    unit: ms
    value: 0.0
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: gh_process_latency
    unit: ms
    value: 1458.7
    statistic: median
    sample_count: 7
  - phase: provider
    scenario: selected_conversation_http
    condition: live
    metric: gh_process_latency
    unit: ms
    value: 1791.8
    statistic: p95
    sample_count: 7
  annotations:
  - kind: finding
    text: One selected Conversation recorded seven gh calls, one 304, five GitHub core charges and
      one GraphQL point.
  - kind: finding
    text: A single checkout job reached three simultaneous gh processes. Coordinator slots bound
      jobs; the report counts the underlying processes.
  - kind: limitation
    text: One exact response, origin checkout acquisition disabled, no competing provider jobs or
      browser timing.
  verdict:
    decision: diagnostic
    primary_metric: provider request report on an exact selected Conversation
    reason: Smoke verification of upstream report coverage on a real server request.
---
# Exp-115: Verify the GitHub Request Report Through the Live Server

The loopback server returned the exact selected Conversation.
Its GitHub report recorded seven `gh` calls, six REST and one GraphQL. One call returned
304\. The report attributed five charges to the primary core quota and one GraphQL
point. The per-process median was 1.46 s. That actual sample had no measurable slot
queue.

At least three `gh` processes overlapped inside one checkout job.
Separate the coordinator’s job slots from process concurrency before changing either.
The [protocol](exp-115-protocol.txt) and [sample](exp-115-live-provider-report.jsonl)
retain the measured counts and provider clocks.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
