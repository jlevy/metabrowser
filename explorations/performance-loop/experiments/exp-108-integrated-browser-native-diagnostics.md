---
title: Integrated Chrome and Native Startup Diagnostics
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-108
  title: Integrated Chrome and Native Startup Diagnostics
  date: '2026-11-26'
  hypotheses:
  - H125
  - H131
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: Chrome first-visit and separate native WKWebView cold startup
  method:
    candidate: 7eac04324971
    record: exp-108-integrated-browser-native-diagnostics.jsonl
    protocol:
      path: exp-108-protocol.txt
      sha256: 38ab4fc4f79dd20badbf5322401f8bdcdb7116fb60810781905f1c24e7981bb6
  observations:
  - phase: startup
    scenario: chrome_commits
    condition: integrated
    metric: server_ready
    unit: ms
    value: 5816
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: chrome_files
    condition: integrated
    metric: landing_ready_observed
    unit: ms
    value: 7962.4
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: chrome_files
    condition: integrated
    metric: browsing_setup_starts
    unit: ms
    value: 10495.8
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: chrome_files
    condition: integrated
    metric: warmup_pending
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.first_show
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 840.2
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.first_show
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.first_show
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.first_show
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.first_show
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 9
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.1
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 450.3
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.1
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.1
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.1
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.1
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.2
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 500.5
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.2
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.2
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.2
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.2
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.3
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 473.7
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.3
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.3
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.3
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.cold.3
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.1
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 90.2
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.1
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.1
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.1
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.1
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.2
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 138
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.2
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.2
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.2
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.revisit.2
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.hover_click
    condition: integrated
    metric: painted_ready
    unit: ms
    value: 390.5
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.hover_click
    condition: integrated
    metric: blank
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.hover_click
    condition: integrated
    metric: placeholder
    unit: frames
    value: 0
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.hover_click
    condition: integrated
    metric: layout_shifts
    unit: count
    value: 1
    statistic: sample
    sample_count: 1
  - phase: browser_navigation
    scenario: commits.hover_click
    condition: integrated
    metric: diff_asset_requests
    unit: requests
    value: 0
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: native_readme
    condition: integrated
    metric: ready
    unit: ms
    value: 1391
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: native_readme
    condition: integrated
    metric: dom_mounted
    unit: ms
    value: 1350
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: native_readme
    condition: integrated
    metric: first_contentful_paint
    unit: ms
    value: 189
    statistic: sample
    sample_count: 1
  - phase: startup
    scenario: native_readme
    condition: integrated
    metric: requests
    unit: requests
    value: 150
    statistic: sample
    sample_count: 1
  annotations:
  - kind: finding
    text: The first Chrome Commits visit had zero blank and placeholder frames. Useful
      content took 840 ms, with nine diff module or stylesheet reads and one layout
      shift.
  - kind: finding
    text: The native probe’s cold README reached useful content in 1.39 seconds.
  - kind: limitation
    text: One valid wiring observation per engine on a busy host, with origin fetching
      disabled.
  verdict:
    decision: diagnostic
    primary_metric: first useful content after ready
    reason: The first-visit and native startup clocks exercise different work and
      each has one observation.
---
# Exp-108: Integrated Chrome and Native Startup Diagnostics

Chrome’s first Commits visit took 840 ms to useful content.
It recorded zero blank or placeholder frames, nine diff assets and one layout shift.
The native WKWebView cold README landing reached useful content in 1.39 s. That clock
covers native startup rather than a Commits click.
Each checked its own readiness condition on the same integrated build, with one
observation per engine and host load above the acceptance guard.

The [protocol](exp-108-protocol.txt) and
[samples](exp-108-integrated-browser-native-diagnostics.jsonl) retain the startup and
click measurements.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
