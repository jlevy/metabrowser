---
type: is
id: is-01m2ma3640mzk65nbbs1tdbhws
title: "Phase 0C.1 contracts: compile deterministic hosted-review schemas"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - contracts
dependencies: []
parent_id: is-01m2krx2resarv4h36yyeje2gj
created_at: 2026-09-16T05:12:37.757Z
updated_at: 2026-09-16T07:13:41.515Z
closed_at: 2026-09-16T07:13:41.515Z
close_reason: "Implemented in 614fef15793ff7cffd0c4e85a577342472fd9686: first-party SoftSchema dependency selection, installed capability registries, 16 enforced contracts, two profiles, cross-runtime evidence, and isolated distribution validation; make verify and GitHub CI are green."
resolution: null
duplicate_of: null
---
Define plugin-local hosted-review contract declarations, deterministic packaged SoftSchema schemas and digests, validate_record, validate_artifact, resource-profile validation, and compile_contracts check mode for every Phase 0 contract. Preserve contract IDs across later neutral-model ownership moves and bind envelopes, formats, models, producers, consumers, browser parsers, and fixtures.

## Notes

Closed inventory: 16 artifacts, 2 resource profiles. Add missing ProviderBinding, ProviderSyncManifest, ProviderViewPointer, and Tombstone IDs; AuthorizationContextRef stays nested. Compile one deterministic enforced schema per artifact with public SoftSchema 0.8.1 APIs. Fix SafeNonNegativeInteger/SafePositiveInteger annotation order so schemas emit minimum/maximum. Keep strict cached-envelope metadata separate from generic SoftSchema validation and always run structural plus Pydantic semantic validation.
