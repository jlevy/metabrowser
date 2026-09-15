---
type: is
id: is-01m2kb2nga7qt6kw5a07s2x7m1
title: "Hosted review Phase 0B.1a: freeze namespace and publication contracts"
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
    target: is-01m2kb31dhpy38zhaf2f42b71r
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:10:34.888Z
updated_at: 2026-09-15T20:10:47.086Z
---
Resolve the Phase 0B.1 contract decisions before code: canonical lowercase ASCII provider kind and DNS host[:port] instance; AuthorizationContextRef identity tuple and canonical JSON digest; auth-independent ProviderBinding; single repository identity authority; closed retrieval outcomes; the exact ProviderSyncManifest/ResourceSet/current/last-complete relationship and required-resource completeness profile; transaction versus collection coverage; query-key projection; remote-consistency variants; deterministic duplicate resolution; tagged continuation; and measurable tombstone corroboration. Update the plan and hosted-review architecture with reviewed field names, nullability, invariants, and ownership. No runtime behavior.
