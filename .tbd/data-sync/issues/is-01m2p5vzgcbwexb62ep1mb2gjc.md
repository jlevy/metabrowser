---
type: is
id: is-01m2p5vzgcbwexb62ep1mb2gjc
title: "GitHub Phase 3A: broker-pinned Git credential lease bridge"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
parent_id: is-01m2h5an32kbkp6zfkhkjzq55f
hold: null
hold_until: null
created_at: 2026-09-16T22:37:16.170Z
updated_at: 2026-09-16T22:47:02.716Z
started_at: 2026-09-16T22:47:02.715Z
---
Implement the provider-neutral-to-Git credential bridge for authenticated selected refs. Keep FetchAuthorizationContext and AuthorizationContextRef as non-secret serializable identity, and add a process-local non-serializable GitFetchCredentialLease issued by the trusted GhCredentialSession. Bind the opaque lease to provider, instance, stable principal, expiry, cancellation generation, and exact provider-declared credential-free HTTPS sources. RepositoryObjectJobPort accepts the matching context plus opaque lease; core validates both before staging and never falls back to ambient Git credentials for ProviderPrincipal work. Keep git/process.py as the sole Git runner and project the credential through a packaged one-shot askpass bridge over bounded inherited pipe or local IPC with terminal prompts disabled. Token bytes never enter plugin-visible values, argv, ordinary environment, files, cache records, refs, logs, or diagnostics. Test context/lease mismatch and expiry, GH_TOKEN-only private-style acquisition with ambient Git auth disabled, ambient principal mismatch, external gh auth switch, broker crash/revocation/cancellation, fork source selection, child reaping, and secret absence.
