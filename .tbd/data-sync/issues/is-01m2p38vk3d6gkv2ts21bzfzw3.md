---
type: is
id: is-01m2p38vk3d6gkv2ts21bzfzw3
title: "Repository Phase 2B review: publish provider-job and selected-ref foundation PR"
kind: task
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:51:52.418Z
updated_at: 2026-09-17T01:36:52.500Z
started_at: 2026-09-16T21:54:38.858Z
---
Independently review and publish one formal provider-job and selected-ref foundation pull request after the repository URL-open PR is green. Base it on the exact green mb-innz head; review the exact diff for job-key isolation, no network under locks, staged fetch validation, full-OID verification, cancellation, attached-checkout non-mutation, the AuthorizationContextRef move into provider_resources, and the separate registry-backed GitFetchCredentialLease boundary. Prove forged or unregistered handles, context/lease mismatch, expiry, revocation, cancellation, and source mismatch for starting and joining requests produce typed secret-free failures, and provider-principal requests fail with git_credentials_unavailable before Git starts until Phase 3A. Run make verify, synchronize beads, use gh stack submit, watch every required check to final green, and register the PR and immutable head with mb-n2ro. Do not merge.
