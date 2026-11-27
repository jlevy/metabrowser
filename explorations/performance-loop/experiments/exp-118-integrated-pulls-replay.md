---
title: Replay Pulls With Separate List and Optional-Tally Readiness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-118
  title: Replay Pulls With Separate List and Optional-Tally Readiness
  date: '2026-11-26'
  hypotheses:
  - H127
  - H128
  - H135
  subject:
    corpus: Public Metabrowser at 7a02fed4b131 with four pinned public pull subjects
    corpus_files: 1286
    host_system: macOS arm64, busy with local verification
    browser: Headless Chrome, live first-visit Pulls
  method:
    candidate: a6731a940a15
    record: exp-118-integrated-pulls-replay.jsonl
    protocol:
      path: exp-118-protocol.txt
      sha256: 8729b557150152852d84f43ba198da9df3c4ce610fcd999b4e62a40866349893
  observations:
  - phase: startup
    scenario: chrome_server
    condition: integrated
    metric: inventory_ready
    value: 12792
    unit: ms
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: checkout_origin
    condition: integrated
    metric: acquisition
    value: 73113.1
    unit: ms
    statistic: sample
    sample_count: 1
  - phase: provider
    scenario: pulls.list_to_pr.cold
    condition: integrated
    metric: provider_slot_wait
    value: 1461.5
    unit: ms
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.first_show
    condition: integrated
    metric: useful_list
    value: 107.5
    unit: ms
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.first_show
    condition: integrated
    metric: optional_navigation_placeholders
    value: 53
    unit: frames
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: integrated
    metric: final_description
    value: 6568.5
    unit: ms
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: integrated
    metric: first_visible_hunk
    value: 38529.5
    unit: ms
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: integrated
    metric: first_visible_hunk
    value: 497.6
    unit: ms
    statistic: sample
    sample_count: 1
  annotations:
  - kind: finding
    text: All 14 transitions converged. The first Pulls list was usable at about 108 ms while optional
      navigation placeholders still appeared in 53 frames.
  - kind: finding
    text: The first selected metadata job waited 1462 ms for provider admission. The origin store
      took 73.1 s. First visible Changes was 38.5 s and a revisit was 498 ms.
  - kind: limitation
    text: One run at high host load and with a changed list readiness definition. No paired comparison
      or live improvement claim.
  verdict:
    decision: diagnostic
    primary_metric: usable first Pulls list and visible Changes
    reason: The instrument admitted the complete real journey and separated list, provider and warm-up
      readings.
---
# Exp-118: Replay Pulls With Separate List and Optional-Tally Readiness

All 14 Chrome transitions passed their guards.
The first Pulls list was usable in 108 ms without blank or preview-placeholder frames.
Its navigation pane still showed optional placeholders in 53 recorded frames.

The first description appeared in 6.57 s and its job waited about 1.46 s for provider
admission. The startup origin store took 73.1 s. The first Changes hunk was visible in
38.5 s, and the revisit took 498 ms.
The browser’s own warm-up count was zero at the browsing boundary while the separate
checkout acquisition was still running.
An origin-warm first-visit run requires an explicit backend gate.

The [protocol](exp-118-protocol.txt) and
[samples](exp-118-integrated-pulls-replay.jsonl) retain the complete journey.
Local verification and high host load limit the latencies to diagnosis.
The corrected first-visit readiness also differs from the earlier refused run’s
definition.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
