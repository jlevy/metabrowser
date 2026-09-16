---
type: is
id: is-01m2kb4fa0swgkhrvw3qq21gtq
title: "Hosted review Phase 0B.1e: model provider binding and hosted repositories"
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
    target: is-01m2kb505pj16mgj8secgn4dex
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:34.079Z
updated_at: 2026-09-16T01:31:32.827Z
closed_at: 2026-09-16T01:31:32.826Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Add ProviderBinding, RepositoryVisibility, HostedRepository, validate/dump entry points, hosted_repository_ref(), validate_provider_binding_successor(), validate_hosted_repository_resource_set(), and validate_repository_successor() to hosted_review/models.py. Keep binding auth-independent and limited to generic entry ID plus RepositoryRef and optional typed provenance. Derive the sole RepositoryRef authority from ProviderObjectRef provider, instance, and opaque ID without forcing a provider-native object_kind spelling. Allow owner/name/default-branch/URL changes across renames while rejecting opaque repository identity changes or silent rebinding. Cover provider-neutral merge-request hosts, HTTPS URLs, canonical timestamps, hostile display strings, and closed-key rejection.

## Notes

Implemented auth-independent ProviderBinding and HostedRepository identity, successor/rename/rebind validation, hosted-repository resource-set validation, portable conformance data, and tests.
