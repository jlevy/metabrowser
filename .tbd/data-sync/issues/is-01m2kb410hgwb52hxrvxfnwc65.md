---
type: is
id: is-01m2kb410hgwb52hxrvxfnwc65
title: "Hosted review Phase 0B.1d: model resource publication and tombstones"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb505pj16mgj8secgn4dex
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:19.440Z
updated_at: 2026-09-15T20:12:07.829Z
---
Add closed transaction, collection coverage, truncation, continuation, snapshot, failure, manifest, ResourceSet, and discriminated tombstone proof models to hosted_review/models.py with validate/dump entry points and validate_resource_set_target(). Enforce immutable staged/committed/failed manifest identity, auth/repository consistency, unique retrieval/snapshot references, current/last-complete eligibility, explicit partial/unavailable/not-requested semantics, and exact same-context tombstone evidence. A lone 404/null, index absence, auth failure, permission loss, rate limit, or never-fetched state must not prove deletion.
