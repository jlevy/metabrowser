---
title: Time a First Pulls Visit After the Origin Store Is Ready
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-120
  title: Time a First Pulls Visit After the Origin Store Is Ready
  date: '2026-11-26'
  hypotheses:
  - H127
  - H135
  - H136
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 with four pinned public pull subjects
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: Headless Chrome first-visit Pulls after product origin warm-up
  method:
    candidate: 3d907d560c8f
    record: exp-120-origin-warm-first-pulls.jsonl
    protocol:
      path: exp-120-protocol.txt
      sha256: 9e8434590a93b2dc23ad0427c715a45f4b7936476876d4f46ae3b73b89630d54
  observations:
  - phase: startup
    scenario: fresh_checkout_origin
    condition: origin_warm
    metric: inventory_ready
    unit: ms
    value: 11067
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: fresh_checkout_origin
    condition: origin_warm
    metric: origin_warmup_after_inventory
    unit: ms
    value: 60533
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.first_show
    condition: origin_warm
    metric: painted_ready
    unit: ms
    value: 173.5
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.first_show
    condition: origin_warm
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.first_show
    condition: origin_warm
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: origin_warm
    metric: painted_ready
    unit: ms
    value: 10159.1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: origin_warm
    metric: blank
    unit: frames
    value: 11
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: origin_warm
    metric: placeholder
    unit: frames
    value: 597
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: origin_warm
    metric: final_description
    unit: ms
    value: 3926
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: origin_warm
    metric: painted_ready
    unit: ms
    value: 717.8
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: origin_warm
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: origin_warm
    metric: placeholder
    unit: frames
    value: 11
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: origin_warm
    metric: first_visible_hunk
    unit: ms
    value: 719.1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: origin_warm
    metric: painted_ready
    unit: ms
    value: 328.2
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: origin_warm
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: origin_warm
    metric: placeholder
    unit: frames
    value: 5
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: origin_warm
    metric: first_visible_hunk
    unit: ms
    value: 328.2
    statistic: sample
    sample_count: 1
  annotations:
  - kind: finding
    text: All 14 transitions passed. The first Changes hunk appeared in 719 ms with zero blank frames.
      Its revisit took 328 ms.
  - kind: finding
    text: The checkout origin wait was 60.53 s before Chrome. The first description took 3.93 s after
      click and the Conversation recorded 11 blank frames.
  - kind: limitation
    text: One prepared diagnostic under load. It does not pair with an as-soon-as-visible run or
      rank a wall-clock implementation change.
  verdict:
    decision: diagnostic
    primary_metric: first visible Changes hunk once the origin is ready
    reason: The real first-visit run verified the declared startup boundary and the measured destination.
---
# Exp-120: Time a First Pulls Visit After the Origin Store Is Ready

The fresh server completed inventory in 11.07 s and then waited 60.53 s for a completed
origin fetch. Chrome started after the backend gate.
All 14 transitions passed.
The first visible Changes hunk on public pull request 888 arrived in 719 ms with zero
blank frames. Its revisit took 328 ms.

Conversation still needs work.
Its description appeared at 3.93 s and the transition recorded 11 blank frames.
A ready origin answers the Git prerequisite; the selected pull request still has to
obtain metadata and paint it.

The [protocol](exp-120-protocol.txt) and
[samples](exp-120-origin-warm-first-pulls.jsonl) keep both startup and navigation
clocks. This busy-host observation uses a different readiness regime from the earlier
as-soon-as-visible Pulls replay.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
