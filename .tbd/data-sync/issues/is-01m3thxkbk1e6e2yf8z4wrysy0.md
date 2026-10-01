---
type: is
id: is-01m3thxkbk1e6e2yf8z4wrysy0
title: Retired provider-store reservations remain in the cache layout, locks and identity
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T01:40:31.729Z
updated_at: 2026-10-01T01:40:31.729Z
---
Found while removing the unused Hosted Review code (PR #246): src/metabrowser/cache/paths.py PROVIDER_BINDINGS and PROVIDER_REPOSITORIES (used by cache/layout.py and cache/projection.py), cache/locks.py LockKind.PROVIDER_RESOURCE and provider_resource_lock, and cache/identity.py provider_repository_store_id are referenced only by tests and the frozen f01 fixtures (state-machines.json, source-identity.json). The thin mirror retired the provider store. Decide whether to remove them (they are in unreleased fixtures and affect layout semantics) or keep them as reserved names with a stated reason. Not labelled v0.12 unless the #246 review says they must go before landing.
