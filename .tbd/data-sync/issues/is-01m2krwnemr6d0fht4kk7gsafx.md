---
type: is
id: is-01m2krwnemr6d0fht4kk7gsafx
title: "Hosted review Phase 0B.3b: review and publish the oracle phase"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b3
dependencies:
  - type: blocks
    target: is-01m2k1jnf5t6bgg340skd537hn
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m2k1jnf5t6bgg340skd537hn
created_at: 2026-09-16T00:11:58.291Z
updated_at: 2026-09-16T00:13:22.943Z
---
Run independent fixture-scrubbing, common-model coverage, architecture, and delivery reviews; address every finding; run make verify; sync beads; and publish exactly one formal draft Phase 0B.3 PR with gh, based on the exact green Phase 0B.2 head. Record base/head OIDs and stack path, watch GitHub CI to a final green summary, and register the PR with mb-n2ro before Phase 0C.1 begins.
