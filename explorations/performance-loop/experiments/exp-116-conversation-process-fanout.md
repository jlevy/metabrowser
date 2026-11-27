---
title: Vary Process Fan-Out for the Same Conversation Reads
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-116
  title: Vary Process Fan-Out for the Same Conversation Reads
  date: '2026-11-26'
  hypotheses:
  - H134
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 and public pull request 888
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, direct live gh API subprocesses
  method:
    candidate: Direct gh CLI with the selected Conversation's three REST parts
    record: exp-116-conversation-process-fanout.jsonl
    protocol:
      path: exp-116-protocol.txt
      sha256: c7c3b9b938580626f6f107823839000a64e1cd84b6b0647978241d3168ddd704
  observations:
  - phase: provider
    scenario: selected_conversation_rest_components
    condition: cap_1
    metric: batch_elapsed
    unit: ms
    value: 6971.1
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_rest_components
    condition: cap_1
    metric: peak_processes
    unit: processes
    value: 1
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_rest_components
    condition: cap_3
    metric: batch_elapsed
    unit: ms
    value: 1314.3
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_rest_components
    condition: cap_3
    metric: peak_processes
    unit: processes
    value: 3
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_rest_components
    condition: cap_2
    metric: batch_elapsed
    unit: ms
    value: 6675.6
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: selected_conversation_rest_components
    condition: cap_2
    metric: peak_processes
    unit: processes
    value: 2
    statistic: sample
    sample_count: 1
  annotations:
  - kind: finding
    text: The three admitted batches returned the same three checked response digests and kept their
      requested process caps.
  - kind: limitation
    text: The second cap-two batch hit the subprocess timeout with no HTTP response headers. The
      remaining attempts were stopped by protocol.
  verdict:
    decision: diagnostic
    primary_metric: wall time for three checked REST responses
    reason: One completed batch per cap and a refused repetition do not rank the alternatives.
---
# Exp-116: Vary Process Fan-Out for the Same Conversation Reads

The admitted batches spent 6.97 s at cap one, 6.68 s at cap two, and 1.31 s at cap
three, with matching response digests.
The second cap-two batch timed out before `gh` returned HTTP headers.
The available remaining-quota readings came from earlier successful calls; the timeout
provides no evidence of a GitHub rate-limit response.

The [protocol](exp-116-protocol.txt) and
[attempts](exp-116-conversation-process-fanout.jsonl) preserve this limit.
Keep the existing process fan-out until a repeatable set of matched, successful batches
can distinguish the costs and tail latencies.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
