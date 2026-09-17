---
type: is
id: is-01m2nz8zzgxsw9yzsgekxy82sr
title: "Hosted review Phase 0D: source bindings and Git object availability"
kind: feature
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2nz98xx1f0js249srp1j39g
  - type: blocks
    target: is-01m2nz9gwd4wyxmrpx49cp9yck
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
hold: null
hold_until: null
created_at: 2026-09-16T20:42:02.606Z
updated_at: 2026-09-17T04:06:27.017Z
started_at: 2026-09-16T21:24:51.780Z
closed_at: 2026-09-17T04:06:27.016Z
close_reason: "Implemented on claude/v011-hosted-review-phase0d at 01584dba (5ab4a930 plus review fixes): source_id bindings with one binding per source and rebind conflicts, RevisionObservation rename, non-persisted LocalObjectAvailability with guarded helpers for revisions and merge commits, corpora, browser parser, schemas, oracle, docs. make verify: 2373 passed, 1 skipped, 124 goldens. Independent review: six findings, all fixed, mutation-verified."
resolution: null
duplicate_of: null
---
Correct the unreleased hosted-review kernel before provider storage ships. Replace ProviderBinding.entry_id and provider-binding retrieval/provenance fields with a conservative credential-free source_id mapped to stable RepositoryRef; permit many sources to bind one repository and reject one source rebinding to a different opaque repository ID. Separate provider-observed revision identity from local repository-store availability with explicit not_requested, present, missing_fetchable, fetch_failed, unavailable, and outside_bound states. Update Pydantic models, SoftSchema contracts, artifact codecs, Python/browser or server-only corpus as applicable, installed inventory, architecture tables, distribution evidence, and negative relationship tests. No compatibility layer: the old records are unreleased.
