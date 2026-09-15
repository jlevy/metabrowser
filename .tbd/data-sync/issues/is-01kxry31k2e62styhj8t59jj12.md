---
type: is
id: is-01kxry31k2e62styhj8t59jj12
title: "Platform: bounded subprocess runner for provider adapters"
kind: feature
status: open
priority: 1
version: 7
spec_path: docs/project/architecture/arch-hosted-review-model.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-07-17T21:00:33.250Z
updated_at: 2026-09-15T01:19:48.830Z
extensions:
  linear:
    id: b2c972be-cc9e-4692-b3ca-d041777ec425
    linked_at: 2026-08-16T08:06:16.208Z
---
Provide a no-shell async subprocess boundary for non-Git provider tools, beginning with gh api: fixed argv, bounded stdin/stdout/stderr, sanitized environment, timeouts, concurrent drain, cancellation/reap, typed failures, and secret-safe diagnostics. Support bounded JSON stdin and separate parsing of included response metadata from body without exposing arbitrary headers. Reuse Git runner invariants without routing gh through the Git-specific API.
