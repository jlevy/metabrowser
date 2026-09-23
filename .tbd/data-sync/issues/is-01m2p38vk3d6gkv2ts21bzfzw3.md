---
type: is
id: is-01m2p38vk3d6gkv2ts21bzfzw3
title: "Repository Phase 2B review: publish provider-job and selected-ref foundation PR"
kind: task
status: closed
priority: 1
version: 20
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
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
updated_at: 2026-09-23T07:37:07.363Z
started_at: 2026-09-16T21:54:38.858Z
closed_at: 2026-09-23T07:37:07.362Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: none; git fetch writes objects before refs, gc is off, and gh owns credentials, so the job protocol, convergence and credential leases are retired."
resolution: null
duplicate_of: null
---
Independently review and publish one formal provider-job and selected-ref foundation pull request after the repository URL-open PR is green. Base it on the exact green mb-innz head; review the exact diff for job-key isolation, no network under locks, staged fetch validation, full-OID verification, cancellation, attached-checkout non-mutation, the AuthorizationContextRef move into provider_resources, and the separate registry-backed GitFetchCredentialLease boundary. Prove forged or unregistered handles, context/lease mismatch, expiry, revocation, cancellation, and source mismatch for starting and joining requests produce typed secret-free failures, and provider-principal requests fail with git_credentials_unavailable before Git starts until Phase 3A. Also review mb-bgn8 bounded background object convergence after serving begins, including startup/completion, cancellation/failure/restart, preservation of cached content, honest partial/converging/complete/failed state, and no implicit network on reads. Run make verify, synchronize beads, use gh stack submit, watch every required check to final green, and register the PR and immutable head with mb-n2ro. Do not merge.

## Notes

2026-09-22 sequence correction: Phase 2B publication also reviews mb-bgn8 bounded background convergence, after the mb-jlon job foundation and mb-innz serving publication. Default-tree prefetch stays in 1B-a. The worker does not block mb-h51g/mb-k900, avoiding the cycle of acquisition waiting for downstream serving. Preserve existing scope and acceptance; no implementation is claimed.
