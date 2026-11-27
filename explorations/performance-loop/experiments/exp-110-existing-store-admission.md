---
title: An Acquired Store Still Needs Comparison Admission
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-110
  title: An Acquired Store Still Needs Comparison Admission
  date: '2026-11-26'
  hypotheses:
  - H127
  subject:
    corpus: Metabrowser synthetic pull-request checkout fixture
    corpus_files: 4
    host_system: macOS arm64, busy
    browser: None, ASGI API with explicit acquisition hold and fake gh
  method:
    candidate: 0a31cfc14223
    record: exp-110-existing-store-admission.jsonl
    protocol:
      path: exp-110-protocol.txt
      sha256: 8425a7e0bb7012141b3b8a703e6426be7c3eb78633e62d0490508c40c85f09c6
  observations:
  - phase: navigation_api
    scenario: checkout_changes_preparation
    condition: available_unattached
    metric: prepare_started
    unit: count
    statistic: sample
    sample_count: 1
    value: 0
  - phase: navigation_api
    scenario: checkout_changes_preparation
    condition: attached_existing
    metric: prepare_started
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: navigation_api
    scenario: checkout_changes_preparation
    condition: attached_existing
    metric: exact_head
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: provider
    scenario: checkout_changes_preparation
    condition: attached_existing
    metric: gh_calls_after_admission
    unit: processes
    statistic: sample
    sample_count: 1
    value: 0
  annotations:
  - kind: finding
    text: The same record revision returned not_due after the store finished and started after binding
      it through the existing list-attach path.
  - kind: finding
    text: The prepared comparison returned the exact fork head. The fake gh transcript was empty
      after admission.
  - kind: limitation
    text: The fixture proves ordering. It does not time acquisition, Git transport, status refresh,
      or the first visible browser hunk.
  verdict:
    decision: diagnostic
    primary_metric: exact idle comparison request admission
    reason: The controlled acquisition exposed one dependency within the first Changes path.
---
# Exp-110: An Acquired Store Still Needs Comparison Admission

A selected pull request first returned its metadata while checkout acquisition was held.
After acquisition finished, the same metadata looked current to the plugin.
The plugin refused the exact idle comparison request because its publication was still
unattached. Binding the existing store via the list path made the record stale and the
same revision eligible.
The comparison returned the expected fork head without starting another fake `gh`
process after admission.
The provider counter covers fake `gh` only.
Git subprocesses and network work were outside that counter.

The [protocol](exp-110-protocol.txt) and
[sample](exp-110-existing-store-admission.jsonl) describe one controlled ASGI replay.
A product experiment still needs to preserve foreground priority and measure the first
expected visible hunk after immediate and idle-dwell clicks.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
