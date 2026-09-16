---
type: is
id: is-01m2kb2nga7qt6kw5a07s2x7m1
title: "Hosted review Phase 0B.1a: freeze namespace and publication contracts"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb31dhpy38zhaf2f42b71r
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:10:34.888Z
updated_at: 2026-09-16T01:31:30.874Z
closed_at: 2026-09-16T01:31:30.873Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Resolve the Phase 0B.1 contract decisions before code: provider-neutral storage namespace; canonical lowercase ASCII provider kind and DNS host[:port] instance; AuthorizationContextRef identity tuple and canonical JSON digest; auth-independent ProviderBinding; single repository identity authority; closed retrieval outcomes; generic provider-object/provider-collection targets; namespaced trusted ResourceProfileSpec declarations outside cached data; the exact ProviderSyncManifest/ResourceSet/current/last-complete relationship; transaction versus collection coverage; query-key projection; remote-consistency variants; deterministic duplicate resolution; generic collection pages; and measurable tombstone proof. Update the plan, external-resource architecture, and hosted-review architecture with reviewed field names, nullability, invariants, and ownership. No runtime behavior.

## Notes

Contract decisions are frozen in the plan and architecture: provider-neutral namespaces, authorization separation, generic resource targets, resource profiles, manifest/pointer semantics, pagination evidence, and deletion proof. Reviewed by the architecture, model, and delivery reviewers; no remaining findings.
