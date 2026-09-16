---
type: is
id: is-01m2kb3g6wktd1ns9zhdcqk6d9
title: "Hosted review Phase 0B.1c: model authorization contexts and retrievals"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb410hgwb52hxrvxfnwc65
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:02.235Z
updated_at: 2026-09-16T01:31:31.850Z
closed_at: 2026-09-16T01:31:31.849Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Extend hosted_review/models.py with AuthorizationMode, AuthorizationContextRef, RetrievalOutcome, typed validator and rate-limit observations, Retrieval, validate/dump entry points, and authorization_context_key(). The key is SHA-256 over canonical JSON of only provider, instance, mode, principal opaque ID, and optional visibility-partition digest. Keep display login, observed scopes/capabilities, times, validators, and rate limits in Retrieval; forbid tokens, argv, raw headers/bodies, auth output, credential paths, and environment values. Cover anonymous/authenticated invariants, stable-key behavior, closed outcomes, not-modified snapshot references, and timestamp/safe-integer reuse.

## Notes

Implemented AuthorizationContextRef, Retrieval, canonical authorization-context keys, closed outcomes, validators/rate-limit observations, secret-shaped extra rejection, and focused conformance tests.
