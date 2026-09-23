---
type: is
id: is-01m2p38vk3d6gkv2ts21bzfzw3
title: "Repository Phase 2B review: publish provider-job and selected-ref foundation PR"
kind: task
status: in_progress
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:51:52.418Z
updated_at: 2026-09-23T01:40:11.355Z
started_at: 2026-09-16T21:54:38.858Z
---
Independently review and publish one formal provider-job and selected-ref foundation pull request after the repository URL-open PR is green. Base it on the exact green mb-innz head; review the exact diff for job-key isolation, no network under locks, staged fetch validation, full-OID verification, cancellation, attached-checkout non-mutation, the AuthorizationContextRef move into provider_resources, and the separate registry-backed GitFetchCredentialLease boundary. Prove forged or unregistered handles, context/lease mismatch, expiry, revocation, cancellation, and source mismatch for starting and joining requests produce typed secret-free failures, and provider-principal requests fail with git_credentials_unavailable before Git starts until Phase 3A. Run make verify, synchronize beads, use gh stack submit, watch every required check to final green, and register the PR and immutable head with mb-n2ro. Do not merge.
