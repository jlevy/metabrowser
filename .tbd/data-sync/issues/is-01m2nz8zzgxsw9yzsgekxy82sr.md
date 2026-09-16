---
type: is
id: is-01m2nz8zzgxsw9yzsgekxy82sr
title: "Hosted review Phase 0D: source bindings and Git object availability"
kind: feature
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
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
updated_at: 2026-09-16T21:24:51.781Z
started_at: 2026-09-16T21:24:51.780Z
---
Correct the unreleased hosted-review kernel before provider storage ships. Replace ProviderBinding.entry_id and provider-binding retrieval/provenance fields with a conservative credential-free source_id mapped to stable RepositoryRef; permit many sources to bind one repository and reject one source rebinding to a different opaque repository ID. Separate provider-observed revision identity from local repository-store availability with explicit not_requested, present, missing_fetchable, fetch_failed, unavailable, and outside_bound states. Update Pydantic models, SoftSchema contracts, artifact codecs, Python/browser or server-only corpus as applicable, installed inventory, architecture tables, distribution evidence, and negative relationship tests. No compatibility layer: the old records are unreleased.
