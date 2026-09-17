---
type: is
id: is-01m2h3vkgbkeq82ch4mzkrch1g
title: "Repository library Phase 2B: provider jobs and selected refs"
kind: task
status: open
priority: 1
version: 33
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2p38vk3d6gkv2ts21bzfzw3
  - type: blocks
    target: is-01m2p5vzgcbwexb62ep1mb2gjc
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-14T23:25:54.570Z
updated_at: 2026-09-17T03:54:08.640Z
started_at: 2026-09-16T21:10:44.862Z
---
Extract provider-facing generic jobs over shared repository stores: per-store progress, coalescing, cancellation and stage outcomes; jobs.py-owned fetch_selected_ref and request_ref_fetch for bounded fetch of explicit refs into a Metabrowser namespace; and full-OID verification before ref publication. Key each job by store, source, closed FetchAuthorizationContext, fetch-policy version, and exact refspec; coalesce only exactly equal proven contexts and never coalesce unknown helper credentials. First move AuthorizationContextRef, authorization_context_key, LocalObjectAvailability, and LocalGitObjectAvailability from builtin_plugins/hosted_review/models.py into provider_resources/models.py with one implementation each, so core never imports a domain plugin (the observation-guarded local-availability helpers stay in hosted_review); the selected-ref service reports local object availability with those moved types; mb-s0gv later moves the remaining neutral records. ProviderPrincipal carries provider kind, instance, stable principal, optional visibility-partition digest, and the derived authorization-context key. At the single RepositoryObjectJobPort boundary, validate the AuthorizationContextRef mode and field combination, derive its key (never accept a caller-supplied key), map it once to that internal variant, and reject an invalid record before job lookup. Define GitFetchCredentialLease as an unforgeable process-local non-serializable handle into a core GitFetchCredentialLeaseRegistry in cache/jobs.py, separate from job identity. validate_git_fetch_credential_lease reads provider, instance, stable principal, authorization-context key, visibility partition, expiry, revocation, cancellation generation, and exact credential-free HTTPS sources from the registry entry, never from the handle, for every request before job lookup, including a request joining in-flight work. A provider-principal Git run uses the starting request's lease; if that request cancels or its lease is revoked, restart once under another attached live lease for an equal authorization-context key or fail the remaining requests typed. Leases authorize a context key, not a broker session. Prove the registry protocol with a test issuer. Until the Phase 3A askpass projection (mb-s123) exists, a provider-principal request with a valid lease fails with git_credentials_unavailable before Git starts, so no ambient credential can be used. selection.py performs no network work. Stage in an isolated temporary repository (or, for jobs without provider credentials, a quarantine) with no lock, then validate object format, expected OID, source, context kind, refspec, and generation before repository-store CAS publication. Never mutate an attached checkout, create a worktree, expose store paths or secrets, or import provider schemas, gh, auth, catalog, chooser, and eviction into core.
