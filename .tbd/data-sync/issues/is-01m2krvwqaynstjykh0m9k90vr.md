---
type: is
id: is-01m2krvwqaynstjykh0m9k90vr
title: "Hosted review Phase 0B.2b: review and publish the record phase"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b2
dependencies:
  - type: blocks
    target: is-01m2k1jkq9cvxx9db7a0z14b0z
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m2k1jkq9cvxx9db7a0z14b0z
created_at: 2026-09-16T00:11:32.969Z
updated_at: 2026-09-16T00:13:22.904Z
---
Run the tbd review, precommit, and PR shortcuts; obtain independent architecture, cross-runtime contract, and delivery reviews; address every finding; run make verify; sync beads; and publish exactly one formal draft Phase 0B.2 PR with gh, based on the exact green Phase 0B.1 head. Record base/head OIDs and the stack path, watch GitHub CI to a final green summary, and register the PR with mb-n2ro before Phase 0B.3 begins.
