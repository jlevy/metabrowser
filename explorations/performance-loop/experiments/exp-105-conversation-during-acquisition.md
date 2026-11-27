---
title: Selected PR Conversation During Checkout Acquisition
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-105
  title: Selected PR Conversation During Checkout Acquisition
  date: '2026-11-26'
  hypotheses:
  - H126
  subject:
    corpus: Synthetic checkout fixture, four served files
    corpus_files: 4
    host_system: macOS arm64
    browser: None, ASGI endpoint with deterministic provider replay
  method:
    control: 9844a59046e1
    candidate: 8b9db5ba944b
    record: exp-105-conversation-during-acquisition.jsonl
    protocol:
      path: exp-105-protocol.txt
      sha256: 09ba05fbff3e5ca69dbb13837428c61ec22d3ae4a87b5c87cfb9f22f840e898c
  observations:
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: control_fresh
    metric: verified_core_before_release
    unit: count
    statistic: sample
    sample_count: 1
    value: 0
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: candidate_fresh
    metric: verified_core_before_release
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: provider
    scenario: checkout_acquisition_held
    condition: candidate_fresh
    metric: core_queries
    unit: requests
    statistic: sample
    sample_count: 1
    value: 1
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: candidate_fresh
    metric: core_survives_handoff
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: candidate_fresh
    metric: comparison_matches_after_release
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: candidate_promoted_prefetch
    metric: verified_core_before_release
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: provider
    scenario: checkout_acquisition_held
    condition: candidate_promoted_prefetch
    metric: core_queries
    unit: requests
    statistic: sample
    sample_count: 1
    value: 1
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: candidate_promoted_prefetch
    metric: core_survives_handoff
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  - phase: navigation_api
    scenario: checkout_acquisition_held
    condition: candidate_promoted_prefetch
    metric: comparison_matches_after_release
    unit: count
    statistic: sample
    sample_count: 1
    value: 1
  annotations:
  - kind: change
    text: A single selected cold Conversation uses the existing metadata read and
      provider slot during first Git acquisition.
  - kind: finding
    text: The held turn blocked the control. A fresh selection and a promoted prefetch
      both returned the verified core before release, issued one core query and kept
      the exact comparison for Changes.
  - kind: finding
    text: The first implementation needed promotion, viewer revocation and store handoff
      guards. Each is covered by a focused regression.
  - kind: limitation
    text: The provider replies and acquisition gate were deterministic fixtures. Live
      elapsed and browser paint are separate pending measurements.
  verdict:
    decision: diagnostic
    primary_metric: verified Conversation before acquisition release
    reason: The forced ordering proves the queue dependency can be removed without
      refetching the core. No live or browser speed verdict follows.
---
# Exp-105: Selected PR Conversation During Checkout Acquisition

The control accepted the selected refresh but could not provide a verified core while
acquisition held the store turn.
The candidate returned the expected reader and pull request body before release.
This held for a fresh request and for a click that joined an optional prefetch already
waiting for the store.
Each used one selected core query.

In both cases, the description survived Git releasing the turn while the metadata read
was still active. A different PR waited for that handoff before attaching the store.
Changes for the initial PR joined its job and resolved the expected comparison head.
A separate regression checked that observing another GitHub reader revokes a live core
and wakes a waiter.

The [protocol](exp-105-protocol.txt) and
[observations](exp-105-conversation-during-acquisition.jsonl) record the API-level
ordering checks. The held gate supplies a cause, with no assumption about real Git or
GitHub duration. Live server and browser timing remain open.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
