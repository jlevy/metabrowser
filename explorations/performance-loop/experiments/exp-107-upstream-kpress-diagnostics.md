---
title: Upstream KPress Sanitizer Diagnostics
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-107
  title: Upstream KPress Sanitizer Diagnostics
  date: '2026-11-26'
  hypotheses:
  - H130
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 and cached public pull request
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, loopback HTTP and CPU microprobe
  method:
    control: 97577adb29d6
    candidate: f6a44d9e1
    record: exp-107-upstream-kpress-diagnostics.jsonl
    protocol:
      path: exp-107-protocol.txt
      sha256: 31a1b51aec7958ea199ce488e725db1a2b4b4bfc8cd6fe91dea198f5719aea71
  observations:
  - phase: navigation_api
    scenario: sanitizer_cpu:README.md
    condition: diagnose
    metric: sanitizer_process_cpu
    unit: ms
    statistic: minimum
    sample_count: 12
    value: 5.163
  - phase: navigation_api
    scenario: sanitizer_cpu:README.md
    condition: diagnose
    metric: sanitizer_process_cpu
    unit: ms
    statistic: median
    sample_count: 12
    value: 5.447
  - phase: navigation_api
    scenario: sanitizer_cpu:README.md
    condition: diagnose
    metric: sanitizer_process_cpu
    unit: ms
    statistic: maximum
    sample_count: 12
    value: 5.97
  - phase: navigation_api
    scenario: sanitizer_cpu:README.md
    condition: no_diagnostics
    metric: sanitizer_process_cpu
    unit: ms
    statistic: minimum
    sample_count: 12
    value: 0.957
  - phase: navigation_api
    scenario: sanitizer_cpu:README.md
    condition: no_diagnostics
    metric: sanitizer_process_cpu
    unit: ms
    statistic: median
    sample_count: 12
    value: 1.065
  - phase: navigation_api
    scenario: sanitizer_cpu:README.md
    condition: no_diagnostics
    metric: sanitizer_process_cpu
    unit: ms
    statistic: maximum
    sample_count: 12
    value: 1.289
  - phase: navigation_api
    scenario: sanitizer_cpu:docs/design-system.md
    condition: diagnose
    metric: sanitizer_process_cpu
    unit: ms
    statistic: minimum
    sample_count: 12
    value: 39.572
  - phase: navigation_api
    scenario: sanitizer_cpu:docs/design-system.md
    condition: diagnose
    metric: sanitizer_process_cpu
    unit: ms
    statistic: median
    sample_count: 12
    value: 43.711
  - phase: navigation_api
    scenario: sanitizer_cpu:docs/design-system.md
    condition: diagnose
    metric: sanitizer_process_cpu
    unit: ms
    statistic: maximum
    sample_count: 12
    value: 53.077
  - phase: navigation_api
    scenario: sanitizer_cpu:docs/design-system.md
    condition: no_diagnostics
    metric: sanitizer_process_cpu
    unit: ms
    statistic: minimum
    sample_count: 12
    value: 4.87
  - phase: navigation_api
    scenario: sanitizer_cpu:docs/design-system.md
    condition: no_diagnostics
    metric: sanitizer_process_cpu
    unit: ms
    statistic: median
    sample_count: 12
    value: 5.298
  - phase: navigation_api
    scenario: sanitizer_cpu:docs/design-system.md
    condition: no_diagnostics
    metric: sanitizer_process_cpu
    unit: ms
    statistic: maximum
    sample_count: 12
    value: 6.627
  - phase: navigation_api
    scenario: seeded_pr_description_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 1689.356
  - phase: navigation_api
    scenario: seeded_pr_description_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 2
    value: 2760.319
  - phase: navigation_api
    scenario: seeded_pr_description_first
    condition: baseline
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 3831.282
  - phase: navigation_api
    scenario: seeded_pr_description_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 1918.131
  - phase: navigation_api
    scenario: seeded_pr_description_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: median
    sample_count: 2
    value: 2745.631
  - phase: navigation_api
    scenario: seeded_pr_description_first
    condition: candidate
    metric: elapsed
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 3573.13
  - phase: startup
    scenario: seeded_pr_server
    condition: baseline
    metric: http_ready
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 8507.322
  - phase: startup
    scenario: seeded_pr_server
    condition: baseline
    metric: http_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 9496.268
  - phase: startup
    scenario: seeded_pr_server
    condition: baseline
    metric: http_ready
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 10485.213
  - phase: startup
    scenario: seeded_pr_server
    condition: candidate
    metric: http_ready
    unit: ms
    statistic: minimum
    sample_count: 2
    value: 4805.831
  - phase: startup
    scenario: seeded_pr_server
    condition: candidate
    metric: http_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 5360.877
  - phase: startup
    scenario: seeded_pr_server
    condition: candidate
    metric: http_ready
    unit: ms
    statistic: maximum
    sample_count: 2
    value: 5915.922
  annotations:
  - kind: change
    text: Upstream KPress 0.3.11 skips sanitizer diagnostics that Metabrowser discards.
  - kind: finding
    text: Sanitizer process CPU fell from 5.45 to 1.06 ms on README HTML and 43.71
      to 5.30 ms on design-system HTML. Output matched exactly.
  - kind: limitation
    text: Cold public PR description HTTP ranges overlapped. Two starts per version
      on a busy host cannot resolve a small end-to-end change.
  - kind: limitation
    text: An initial HTTP attempt was refused because the copied seed had a dangling
      shallow-file link. The retry used a new copy with that link omitted.
  verdict:
    decision: diagnostic
    primary_metric: first seeded PR description through the real server
    reason: Matched responses and lower isolated CPU establish the removed work. The
      cold HTTP timing does not establish an end-to-end gain.
---
# Exp-107: Upstream KPress Sanitizer Diagnostics

Upstream upgraded KPress from 0.3.10 to 0.3.11 and disabled diagnostics in the projected
Markdown sanitizer. The isolated CPU probe changed only that option.
Its median fell from 5.45 to 1.06 ms on README HTML and from 43.71 to 5.30 ms on the
larger design-system document, with identical sanitized output across 12 calls per mode
on each input.

First public PR description HTTP times overlapped.
Two control starts took 1.69 and 3.83 s, and two candidate starts took 1.92 and 3.57 s,
with matching checked HTML. The host was busy.
This experiment assigns no end-to-end or browser verdict.

The [protocol](exp-107-protocol.txt) records the seed refusal and the follow-up CPU
test. The [samples](exp-107-upstream-kpress-diagnostics.jsonl) keep the two regimes
available for separate charts.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
