---
type: is
id: is-01m2kb31dhpy38zhaf2f42b71r
title: "Hosted review Phase 0B.1b: canonicalize provider namespace scalars"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb3g6wktd1ns9zhdcqk6d9
  - type: blocks
    target: is-01m2kb4fa0swgkhrvw3qq21gtq
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:10:47.086Z
updated_at: 2026-09-16T01:31:31.364Z
closed_at: 2026-09-16T01:31:31.363Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Add shared ProviderKind and ProviderInstance scalar validation to hosted_review/models.py and apply it to ProviderObjectRef and RepositoryRef. Require lowercase ASCII provider tokens and canonical lowercase DNS host[:port] instance spelling. Update the exact production hosted-review-model.js parser and the shared ChangeRequest corpus in the same change so Phase 0A Python/JavaScript parity never drifts. Add invalid case, mixed-case, Unicode, port, and cross-provider relationship evidence without adding a route, manifest, network call, cache, or dependency.

## Notes

Implemented canonical ProviderKind and ProviderInstance validation in Python and the production JavaScript parser, with shared corpus coverage for case, Unicode, ports, provider relationships, and invalid namespaces.
