---
type: is
id: is-01kxry31k2e62styhj8t59jj12
title: "Platform: bounded subprocess runner for provider adapters"
kind: feature
status: closed
priority: 1
version: 22
spec_path: docs/project/architecture/arch-hosted-review-model.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
  - type: blocks
    target: is-01m2p5vzgcbwexb62ep1mb2gjc
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-07-17T21:00:33.250Z
updated_at: 2026-09-23T07:37:12.127Z
started_at: 2026-09-16T22:03:41.555Z
closed_at: 2026-09-23T07:37:12.126Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-nkmq (PR data via gh runner and JSON records); the token broker, askpass bridge, provider snapshot store, adapter registry, binding and rebind are retired."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: b2c972be-cc9e-4692-b3ca-d041777ec425
    linked_at: 2026-08-16T08:06:16.208Z
---
Provide a no-shell async subprocess boundary for non-Git provider tools, beginning with gh api: fixed argv, bounded stdin/stdout/stderr, sanitized environment, timeouts, concurrent drain, cancellation/reap, typed failures, and secret-safe diagnostics. Add a short-lived trusted GhCredentialSession broker that selects an explicit gh login, obtains its token once with gh auth token, retains credential state only in broker memory, injects it only into child gh api environments, and disposes it on exit. The broker also implements issue_git_fetch_credential_lease: it registers short-lived GitFetchCredentialLease entries in the Phase 2B core registry, bound to provider kind, instance, stable principal, authorization-context key, visibility partition, expiry, cancellation generation, and exact provider-declared credential-free HTTPS sources, keeps them live until every Git run using them finishes, then revokes them (immediately on crash or cancellation). It exposes a session-owned credential answer hook that answers only runs core armed for one run, lease, and source URL through mb-s123's askpass bridge and never sends token bytes to plugins or the parent application. The parent receives only bounded response frames, opaque lease registrations, and typed failures. Support bounded JSON stdin and separate parsing of included response metadata from body. Test broker loss, lease revocation on exit, external account switch, child cancellation and reaping, and absence of tokens from argv, ordinary environment, files, logs, records, and diagnostics. Reuse Git runner invariants without routing gh through the Git-specific API.
