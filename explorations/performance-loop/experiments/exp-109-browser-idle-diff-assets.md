---
title: Prepare the Git Diff Assets During Browser Idle
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-109
  title: Prepare the Git Diff Assets During Browser Idle
  date: '2026-11-26'
  hypotheses:
  - H131
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: Chrome first-visit Commits
  method:
    control: 7eac04324971
    candidate: b86917ee85bb
    interleaved: true
    runs_per_condition: 2
    record: exp-109-browser-idle-diff-assets.jsonl
    protocol:
      path: exp-109-protocol.txt
      sha256: a286653476e29da16eff5696cfaeca18bd064a133702fb4133b1a1a1715bfd32
  observations:
  - phase: startup
    scenario: chrome_server
    condition: control
    metric: server_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 8886.0
  - phase: startup
    scenario: chrome_files
    condition: control
    metric: landing_ready_observed
    unit: ms
    statistic: median
    sample_count: 2
    value: 5114.35
  - phase: startup
    scenario: chrome_files
    condition: control
    metric: browsing_setup_starts
    unit: ms
    statistic: median
    sample_count: 2
    value: 7696.15
  - phase: startup
    scenario: chrome_files
    condition: control
    metric: warmup_pending
    unit: requests
    statistic: median
    sample_count: 2
    value: 0.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: control
    metric: diff_asset_requests
    unit: requests
    statistic: median
    sample_count: 2
    value: 9.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: control
    metric: painted_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 952.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: control
    metric: blank
    unit: frames
    statistic: median
    sample_count: 2
    value: 0.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: control
    metric: placeholder
    unit: frames
    statistic: median
    sample_count: 2
    value: 0.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: control
    metric: movement
    unit: px
    statistic: median
    sample_count: 2
    value: 37.0
  - phase: startup
    scenario: chrome_server
    condition: candidate
    metric: server_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 4089.5
  - phase: startup
    scenario: chrome_files
    condition: candidate
    metric: landing_ready_observed
    unit: ms
    statistic: median
    sample_count: 2
    value: 4873.5
  - phase: startup
    scenario: chrome_files
    condition: candidate
    metric: browsing_setup_starts
    unit: ms
    statistic: median
    sample_count: 2
    value: 7402.7
  - phase: startup
    scenario: chrome_files
    condition: candidate
    metric: warmup_pending
    unit: requests
    statistic: median
    sample_count: 2
    value: 0.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: candidate
    metric: diff_asset_requests
    unit: requests
    statistic: median
    sample_count: 2
    value: 1.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: candidate
    metric: painted_ready
    unit: ms
    statistic: median
    sample_count: 2
    value: 803.25
  - phase: browser_navigation
    scenario: commits.first_show
    condition: candidate
    metric: blank
    unit: frames
    statistic: median
    sample_count: 2
    value: 0.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: candidate
    metric: placeholder
    unit: frames
    statistic: median
    sample_count: 2
    value: 0.0
  - phase: browser_navigation
    scenario: commits.first_show
    condition: candidate
    metric: movement
    unit: px
    statistic: median
    sample_count: 2
    value: 37.0
  annotations:
  - kind: change
    text: After Git discovery, queue the existing diff renderer through the idle SDK.
  - kind: finding
    text: The first Commits click requested one diff asset with preparation versus nine in both controls.
      The remaining request was diff-type-filter.js.
  - kind: finding
    text: All four clicks recorded zero blank and placeholder frames and 37 px of movement.
  - kind: limitation
    text: Both paint and Files readiness overlapped. Only two runs per condition were taken, at very
      high load, with the origin store and GitHub disabled.
  - kind: finding
    text: Dropped the implementation because a refused speculative import can disable a later interactive
      diff in the same document.
  verdict:
    decision: diagnostic
    primary_metric: first Commits click diff asset requests
    reason: The request shift reproduced. Paint and startup timings overlapped and the idle loader
      could retain a transient failure.
---
# Exp-109: Prepare the Git Diff Assets During Browser Idle

Preparing the shared renderer moved eight static requests out of the first Commits click
in both pairs. Control clicks requested nine diff assets.
Candidate clicks requested one, `diff-type-filter.js`. All four clicks showed zero blank
or placeholder frames and 37 px of movement.
The candidate leaves the first history page in charge of choosing the commit.

The control reached useful Commits content in 1,145 and 759 ms.
The candidate took 600 and 1,006 ms.
Files landing times also overlapped.
Both conditions had zero warm-up requests pending at the start of browsing setup.
High host load, two samples per condition and disabled origin fetching make the timing
diagnostic.

The branch drops this implementation.
The loader remembers a rejected module import for the life of the document, including
one started speculatively.
Its stylesheet cache also remembers failed loads as complete.
A later click would still see the failed attempt after the network recovered.
Chrome’s idle hook can also start before the first view settles.
A later experiment can try transfer-only hints with a failed prefetch followed by a
successful interactive load.

The [protocol](exp-109-protocol.txt) and
[samples](exp-109-browser-idle-diff-assets.jsonl) keep startup and navigation on their
own clocks.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
