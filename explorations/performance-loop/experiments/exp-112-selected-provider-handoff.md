---
title: Give Selected Conversation Metadata the Next Free Provider Slot
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-112
  title: Give Selected Conversation Metadata the Next Free Provider Slot
  date: '2026-11-26'
  hypotheses:
  - H128
  subject:
    corpus: Metabrowser synthetic checkout PR fixture
    corpus_files: 4
    host_system: macOS arm64
    browser: None, exact ASGI route and fake gh provider
  method:
    control: 4b6a4fef3f5c
    candidate: Selected slot handoff paired with this record
    record: exp-112-selected-provider-handoff.jsonl
    protocol:
      path: exp-112-protocol.txt
      sha256: cdf8da8e5851fc92597c63a1aec6e6ed93933140dd5f2c1db296c2b04de9ddd3
  observations:
  - phase: provider
    scenario: selected_conversation_during_acquisition
    condition: fifo
    metric: optional_admitted_before_selection
    unit: count
    statistic: sample
    sample_count: 2
    value: 2
  - phase: provider
    scenario: selected_conversation_during_acquisition
    condition: selected_first
    metric: optional_admitted_before_selection
    unit: count
    statistic: sample
    sample_count: 2
    value: 0
  - phase: provider
    scenario: selected_conversation_during_acquisition
    condition: selected_first
    metric: core_query_count
    unit: requests
    statistic: sample
    sample_count: 2
    value: 1
  - phase: provider
    scenario: selected_conversation_during_acquisition
    condition: selected_first
    metric: exact_changes_after_release
    unit: count
    statistic: sample
    sample_count: 2
    value: 1
  annotations:
  - kind: change
    text: Selected Conversation metadata alone can pass queued provider work during initial checkout
      acquisition. The shared slot cap and in-flight admissions remain in effect.
  - kind: finding
    text: Both FIFO controls admitted two optional jobs first. Both candidates showed the exact selected
      description first and completed optional work in order afterwards.
  - kind: limitation
    text: Fixed ordering under deterministic slot contention. No paired live wall-clock or rate consumption
      estimate.
  verdict:
    decision: diagnostic
    primary_metric: optional admissions before exact selected Conversation
    reason: Both API replay cases establish the intended admission order without relying on wall-clock
      comparisons.
---
# Exp-112: Give Selected Conversation Metadata the Next Free Provider Slot

When the first Git acquisition holds one slot and background work holds the other, the
selected Conversation waits at the same provider gate.
The FIFO replay gave the released slot to two optional jobs before the selected request,
for both a first selection and a promoted queued prefetch.

The candidate gave the released slot to the selected request both times.
It returned the exact verified description with one core query.
Both optional jobs completed in their original order afterwards.
The same request obtained the expected Changes head when the Git turn was released.

Under continued contention, the gate admits an ordinary waiter after two selected
handoffs pass it. Cancellation before or after a handoff returns availability without
interrupting an in-flight provider request.
Upstream’s request report records slot admission delay on the job as `queued_ms`,
separate from GitHub round trips.

The [protocol](exp-112-protocol.txt) and
[samples](exp-112-selected-provider-handoff.jsonl) record a controlled API replay.
A live run still needs to quantify the time saved.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
