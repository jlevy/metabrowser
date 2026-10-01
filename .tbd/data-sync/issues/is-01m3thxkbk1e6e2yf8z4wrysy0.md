---
type: is
id: is-01m3thxkbk1e6e2yf8z4wrysy0
title: Retired provider-store reservations remain in the cache layout, locks and identity
kind: task
status: in_progress
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T01:40:31.729Z
updated_at: 2026-10-01T01:56:48.287Z
started_at: 2026-10-01T01:56:43.688Z
---
Found while removing the unused Hosted Review code (PR #246): src/metabrowser/cache/paths.py PROVIDER_BINDINGS and PROVIDER_REPOSITORIES (used by cache/layout.py and cache/projection.py), cache/locks.py LockKind.PROVIDER_RESOURCE and provider_resource_lock, and cache/identity.py provider_repository_store_id are referenced only by tests and the frozen f01 fixtures (state-machines.json, source-identity.json). The thin mirror retired the provider store. Decide whether to remove them (they are in unreleased fixtures and affect layout semantics) or keep them as reserved names with a stated reason. Not labelled v0.12 unless the #246 review says they must go before landing.

## Notes

2026-09-30: the #246 review confirmed PROVIDER_BINDINGS/PROVIDER_REPOSITORIES are read by cache/layout.py and cache/projection.py but nothing writes them; the lock kind and store-id helper are test-only. None exists on main, so they go in PR #246 as their own commit, with the fixture edits; the reference branch (#247) keeps them.
