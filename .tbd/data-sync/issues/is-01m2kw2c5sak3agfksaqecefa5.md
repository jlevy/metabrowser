---
type: is
id: is-01m2kw2c5sak3agfksaqecefa5
title: "GitHub Phase 3B review: publish direct PR cache PR"
kind: task
status: open
priority: 1
version: 16
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kw2cra83fyszkrptvhfead
  - type: blocks
    target: is-01kxry30twkcz9sg4ecahcg63j
  - type: blocks
    target: is-01m2h9jjh45d8db9rbd0qtscf7
  - type: blocks
    target: is-01m2ktkve5n2fztx8smd6n9vja
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-16T01:07:31.128Z
updated_at: 2026-09-20T16:48:25.336Z
started_at: 2026-09-16T21:10:44.943Z
---
Independently review the directly addressed PR bundle, shared provider mirror reuse, selected Git OIDs, provider and Git consistency, offline reuse, partiality, and publication. Resolve findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green provider-foundation head. Record exact PR, base, head, OIDs, formal stack view, review, final green CI, and mb-n2ro registration. Do not merge.
