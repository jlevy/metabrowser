---
title: Wait for the Checkout Origin Before Timing First Visits
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-119
  title: Wait for the Checkout Origin Before Timing First Visits
  date: '2026-11-26'
  hypotheses:
  - H136
  subject:
    corpus: Public Metabrowser checkout at 7a02fed4b131
    corpus_files: 1286
    host_system: macOS arm64, busy
    browser: None, real loopback server and passive origin readiness check
  method:
    candidate: a6731a940a15 with the measured origin gate helper
    record: exp-119-origin-warmup-gate.jsonl
    protocol:
      path: exp-119-protocol.txt
      sha256: b118831510297a658e4007801812e0a09fedce05031c39d37817ed890e4e137e
  observations:
  - phase: startup
    scenario: fresh_checkout_origin
    condition: read_only_gate
    metric: inventory_ready
    unit: ms
    statistic: sample
    sample_count: 1
    value: 12451
  - phase: startup
    scenario: fresh_checkout_origin
    condition: read_only_gate
    metric: origin_warmup_after_inventory
    unit: ms
    statistic: sample
    sample_count: 1
    value: 57729
  annotations:
  - kind: finding
    text: Inventory was ready in 12.45 s. The passive origin gate then waited 57.73 s for a fresh
      completed fetch.
  - kind: change
    text: The first-visit runner can record backend origin readiness before creating a browser profile.
  - kind: limitation
    text: One startup-only smoke under load. The option verifies one explicit prerequisite and makes
      no latency claim.
  verdict:
    decision: diagnostic
    primary_metric: origin startup wait after inventory ready
    reason: A real server reported separate inventory and origin readiness phases without starting
      a browser.
---
# Exp-119: Wait for the Checkout Origin Before Timing First Visits

Inventory was complete at 12.45 s. The checkout-origin store became ready 57.73 s later.
The probe waited on the same read-only status that the Chrome runner uses for
`--wait-origin-ready`. It did not open Chrome or request a refresh.

The [protocol](exp-119-protocol.txt) and [sample](exp-119-origin-warmup-gate.jsonl)
separate both startup phases.
The fixture also verifies that the gate refuses missing or still-warming origins.
First-visit runs without this gate remain available for measuring how browsing behaves
during product warm-up.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
