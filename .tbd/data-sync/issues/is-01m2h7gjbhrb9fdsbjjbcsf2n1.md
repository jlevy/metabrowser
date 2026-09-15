---
type: is
id: is-01m2h7gjbhrb9fdsbjjbcsf2n1
title: "GitHub Phase 3A: provider binding and repository summary snapshot"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-15T00:29:47.247Z
updated_at: 2026-09-15T01:31:31.348Z
---
Bind one generic cache entry to a stable GitHub repository ID under a stable AuthorizationContextRef without changing generic source identity. Discover GitHub through mb-ji83 and publish HostedRepository/v1, Retrieval/v1, and a committed sync manifest through the mb-i3xc store kernel: digest only stable auth identity, keep display login/scopes/observation time in Retrieval/v1, refuse authenticated publication without a stable opaque principal ID, and use auth-scoped current/last-complete pointers, reader leases, fixed lock order, and revalidated entry/auth context after lock-free acquisition. Keep raw responses and credentials out of durable state; expose the logical summary through plugin routes and CLI parity.
