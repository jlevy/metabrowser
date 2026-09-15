---
type: is
id: is-01m2kb3g6wktd1ns9zhdcqk6d9
title: "Hosted review Phase 0B.1c: model authorization contexts and retrievals"
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
    target: is-01m2kb410hgwb52hxrvxfnwc65
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:02.235Z
updated_at: 2026-09-15T20:11:19.440Z
---
Extend hosted_review/models.py with AuthorizationMode, AuthorizationContextRef, RetrievalOutcome, typed validator and rate-limit observations, Retrieval, validate/dump entry points, and authorization_context_key(). The key is SHA-256 over canonical JSON of only provider, instance, mode, principal opaque ID, and optional visibility-partition digest. Keep display login, observed scopes/capabilities, times, validators, and rate limits in Retrieval; forbid tokens, argv, raw headers/bodies, auth output, credential paths, and environment values. Cover anonymous/authenticated invariants, stable-key behavior, closed outcomes, not-modified snapshot references, and timestamp/safe-integer reuse.
