---
title: Separate the First Visible Changes Hunk From File-Card Readiness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-111
  title: Separate the First Visible Changes Hunk From File-Card Readiness
  date: '2026-11-26'
  hypotheses:
  - H127
  - H128
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131 and public PRs 888, 882, 887, 880
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: Headless Chrome first-visit Pulls, live GitHub
  method:
    candidate: e5600bee5923
    record: exp-111-visible-changes-hunk.jsonl
    protocol:
      path: exp-111-protocol.txt
      sha256: c3c730ff2ea8eb82daa30143715ee60032fccc5c0d97bf8b60b3d2b0c7283354
  observations:
  - phase: startup
    scenario: chrome_server
    condition: integrated
    metric: server_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 2329
  - phase: startup
    scenario: chrome_files
    condition: integrated
    metric: landing_ready_observed
    unit: ms
    statistic: sample
    sample_count: 1
    value: 1335.2
  - phase: startup
    scenario: chrome_files
    condition: integrated
    metric: browsing_setup_starts
    unit: ms
    statistic: sample
    sample_count: 1
    value: 3959.3
  - phase: startup
    scenario: chrome_files
    condition: integrated
    metric: browser_warmup_pending
    unit: requests
    statistic: sample
    sample_count: 1
    value: 0
  - phase: startup
    scenario: checkout_origin
    condition: integrated
    metric: acquire_git_store
    unit: ms
    statistic: sample
    sample_count: 1
    value: 32212.1
  - phase: startup
    scenario: checkout_origin
    condition: integrated
    metric: wildcard_ref_fetch
    unit: ms
    statistic: sample
    sample_count: 1
    value: 30423.7
  - phase: provider
    scenario: pulls.tab.changes_first
    condition: integrated
    metric: origin_store_completion_since_click
    unit: ms
    statistic: sample
    sample_count: 1
    value: 6240.0
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: integrated
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 8149.2
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: integrated
    metric: blank
    unit: frames
    statistic: sample
    sample_count: 1
    value: 7
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: integrated
    metric: placeholder
    unit: frames
    statistic: sample
    sample_count: 1
    value: 374
  - phase: browser_navigation
    scenario: pulls.list_to_pr.cold
    condition: integrated
    metric: final_description
    unit: ms
    statistic: sample
    sample_count: 1
    value: 6532.6
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: integrated
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 9753.6
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: integrated
    metric: blank
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: integrated
    metric: placeholder
    unit: frames
    statistic: sample
    sample_count: 1
    value: 564
  - phase: browser_navigation
    scenario: pulls.tab.changes_first
    condition: integrated
    metric: first_visible_hunk
    unit: ms
    statistic: sample
    sample_count: 1
    value: 9753.6
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: integrated
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 291
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: integrated
    metric: blank
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: integrated
    metric: placeholder
    unit: frames
    statistic: sample
    sample_count: 1
    value: 5
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit
    condition: integrated
    metric: first_visible_hunk
    unit: ms
    statistic: sample
    sample_count: 1
    value: 324.3
  - phase: browser_navigation
    scenario: pulls.pr_to_pr.hover_click
    condition: integrated
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 5213.3
  - phase: browser_navigation
    scenario: pulls.pr_to_pr.hover_click
    condition: integrated
    metric: blank
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.pr_to_pr.hover_click
    condition: integrated
    metric: placeholder
    unit: frames
    statistic: sample
    sample_count: 1
    value: 306
  - phase: browser_navigation
    scenario: pulls.pr_to_pr.hover_click
    condition: integrated
    metric: final_description
    unit: ms
    statistic: sample
    sample_count: 1
    value: 263.4
  - phase: browser_navigation
    scenario: pulls.tab.changes_first_2
    condition: integrated
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 109.1
  - phase: browser_navigation
    scenario: pulls.tab.changes_first_2
    condition: integrated
    metric: blank
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_first_2
    condition: integrated
    metric: placeholder
    unit: frames
    statistic: sample
    sample_count: 1
    value: 2
  - phase: browser_navigation
    scenario: pulls.tab.changes_first_2
    condition: integrated
    metric: first_visible_hunk
    unit: ms
    statistic: sample
    sample_count: 1
    value: 125.7
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit_2
    condition: integrated
    metric: painted_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 86.2
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit_2
    condition: integrated
    metric: blank
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit_2
    condition: integrated
    metric: placeholder
    unit: frames
    statistic: sample
    sample_count: 1
    value: 0
  - phase: browser_navigation
    scenario: pulls.tab.changes_revisit_2
    condition: integrated
    metric: first_visible_hunk
    unit: ms
    statistic: sample
    sample_count: 1
    value: 102.9
  annotations:
  - kind: finding
    text: 'The first #888 hunk took 9754 ms. Revisiting it took 324 ms, after the file-card ready
      reading at 291 ms.'
  - kind: finding
    text: 'The origin store acquired during startup and finished 6240 ms after the #888 Changes click.
      It included a 30424 ms wildcard Git fetch.'
  - kind: finding
    text: 'The #887 description appeared at 263 ms, while its broader Conversation readiness took
      5213 ms.'
  - kind: limitation
    text: The first Pulls-list step failed convergence. The remaining individually timed transitions
      are diagnostic, with one run on a busy host.
  verdict:
    decision: diagnostic
    primary_metric: first visible hunk on the selected pull request
    reason: The milestone distinguished three stages in a refused live smoke and reported the startup
      dependency separately.
---
# Exp-111: Separate the First Visible Changes Hunk From File-Card Readiness

The first Changes click on PR #888 reached visible source in 9.75 s. Revisiting the same
tab showed source in 324 ms, 33 ms after file-card readiness.
PR #887 showed its description at 263 ms while the whole Conversation view still took
5.21 s to clear its readiness check.
These are distinct clocks.

The origin store’s startup acquisition took 32.2 s, including 30.4 s for the wildcard
heads and tags Git fetch.
It finished 6.24 s after the first Changes click.
The comparison job finished about 360 ms after that.
The first hunk appeared another 3.15 s later, after the comparison routes and browser
rendering had run.

The Pulls-list guard refused the sample because the list or prompt failed to converge.
The retained browser observations describe individual transitions in that refused
journey.
GitHub returned the authenticated core and GraphQL quota snapshots in the sample
file. Other callers shared the account, so those snapshots cannot count this journey’s
provider calls.

The [protocol](exp-111-protocol.txt) and
[observations](exp-111-visible-changes-hunk.jsonl) keep product warm-up, external
fetching and browser milestones on their own clocks.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
