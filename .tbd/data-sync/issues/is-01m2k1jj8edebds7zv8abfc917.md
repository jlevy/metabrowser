---
type: is
id: is-01m2k1jj8edebds7zv8abfc917
title: "Hosted review Phase 0B.1: complete provider storage and repository records"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jkq9cvxx9db7a0z14b0z
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:30.089Z
updated_at: 2026-09-15T17:24:31.585Z
---
Extend models.py and the portable corpus with ProviderBinding, stable AuthorizationContextRef, Retrieval, ProviderSyncManifest, ResourceSet, Tombstone, HostedRepository, and query-keyed ChangeRequestIndex. Add semantic validators for stable auth identity versus volatile observations, transaction and collection states, pagination consistency, partiality, remote consistency, tombstone proof, and immutable repository identity. No provider acquisition or filesystem store.
