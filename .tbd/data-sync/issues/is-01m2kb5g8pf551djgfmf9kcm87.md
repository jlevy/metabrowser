---
type: is
id: is-01m2kb5g8pf551djgfmf9kcm87
title: "Hosted review Phase 0B.1g: add portable storage, repository, and index corpora"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb6031dk9t2pzt5d35fvyd
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:12:07.829Z
updated_at: 2026-09-15T20:12:24.032Z
---
Package provider-storage-conformance.json, hosted-repository-conformance.json, and change-request-index-conformance.json; generalize tests/hosted_review_cases.py mutation/loading helpers; and extend focused model/conformance tests. Cover auth-key stability and separation, secret-shaped extra rejection, transaction/coverage combinations, current/last-complete eligibility, same-context tombstone evidence, rename versus rebind, query-key inputs, empty/partial indexes, bounds, cursor continuity, duplicate identity, remote consistency, direct/index identity agreement, hostile text, explicit nulls, and JSON round-trips. Keep fixtures provider-neutral and public-safe; Phase 0C later runs them through JavaScript and compiled SoftSchema.
