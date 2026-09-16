---
type: is
id: is-01kxry31k2e62styhj8t59jj12
title: "Platform: bounded subprocess runner for provider adapters"
kind: feature
status: open
priority: 1
version: 10
spec_path: docs/project/architecture/arch-hosted-review-model.md
delegate: null
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-07-17T21:00:33.250Z
updated_at: 2026-09-16T22:04:18.033Z
started_at: 2026-09-16T22:03:41.555Z
extensions:
  linear:
    id: b2c972be-cc9e-4692-b3ca-d041777ec425
    linked_at: 2026-08-16T08:06:16.208Z
---
Provide a no-shell async subprocess boundary for non-Git provider tools, beginning with gh api: fixed argv, bounded stdin/stdout/stderr, sanitized environment, timeouts, concurrent drain, cancellation/reap, typed failures, and secret-safe diagnostics. Add a short-lived trusted GhCredentialSession broker that selects an explicit gh login, obtains its token once with gh auth token, retains credential state only in broker memory, injects it only into child gh api environments, and disposes it on exit. The parent receives only bounded response frames and typed failures. Support bounded JSON stdin and separate parsing of included response metadata from body without exposing arbitrary headers, tokens, child environments, or raw errors. Reuse Git runner invariants without routing gh through the Git-specific API.
