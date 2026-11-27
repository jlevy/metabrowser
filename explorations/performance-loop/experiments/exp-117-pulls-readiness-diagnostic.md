---
title: Distinguish an Optional Pulls Tally From List Readiness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-117
  title: Distinguish an Optional Pulls Tally From List Readiness
  hypotheses:
  - H135
  date: '2026-11-26'
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: Headless Chrome first-visit Pulls
  method:
    control: The original first-visit Pulls-list readiness predicate
    candidate: First-visit readiness with the named optional badge omitted
    record: exp-117-pulls-readiness-diagnostic.jsonl
    protocol:
      path: exp-117-protocol.txt
      sha256: 64c1ef0a75e0c8d2a686ccf1f78fcb77bcb395aa25172e84351b998b4d3be530
  observations:
  - phase: browser_navigation
    scenario: pulls_first_show_optional_tally
    condition: live_diagnostic
    metric: mounted_rows_during_optional_tally
    unit: count
    value: 25
    statistic: sample
    sample_count: 1
  annotations:
  - kind: finding
    text: The list had 25 usable rows and its prompt while the optional changed-lines badge was pending.
  - kind: change
    text: First-visit readiness allows that exact aria-hidden badge. Placeholder telemetry still
      counts it, and the standard benchmark keeps its stricter readiness.
  - kind: limitation
    text: This observes readiness and documents the condition. It neither measures nor removes a
      late badge repaint.
  verdict:
    decision: diagnostic
    primary_metric: usable Pulls rows during optional tally
    reason: The observed badge was optional and the underlying list and prompt were present.
---
# Exp-117: Distinguish an Optional Pulls Tally From List Readiness

After the Files landing the Pulls tab showed its preview prompt and 25 mounted rows
while an optional changed-lines badge was pending.
The original first-visit readiness required every placeholder in the list to be gone.
The adjusted first-visit check allows only the observed aria-hidden badge to remain.
It still needs the list and prompt, and frame telemetry still counts the badge.
The standard readiness regime keeps its original check.

The [protocol](exp-117-protocol.txt) and
[samples](exp-117-pulls-readiness-diagnostic.jsonl) record the usable-list condition.
The new regime flag keeps this definition separate from earlier first-visit evidence.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
