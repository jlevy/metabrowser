---
type: is
id: is-01m2h3vkgbkeq82ch4mzkrch1g
title: "Repository library Phase 2B: provider jobs and selected refs"
kind: task
status: closed
priority: 1
version: 40
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
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
  - type: blocks
    target: is-01m35ypert7n967xft0evk0qwc
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-14T23:25:54.570Z
updated_at: 2026-09-23T07:37:05.417Z
started_at: 2026-09-16T21:10:44.862Z
closed_at: 2026-09-23T07:37:05.412Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: none; git fetch writes objects before refs, gc is off, and gh owns credentials, so the job protocol, convergence and credential leases are retired."
resolution: null
duplicate_of: null
---
Extract provider-facing generic jobs over shared repository stores: per-store progress, coalescing, cancellation and stage outcomes; jobs.py-owned fetch_selected_ref and request_ref_fetch for bounded fetch of explicit refs into a Metabrowser namespace; and full-OID verification before ref publication. Key each job by store, source, closed FetchAuthorizationContext, fetch-policy version, and exact refspec; coalesce only exactly equal proven contexts and never coalesce unknown helper credentials. First move AuthorizationContextRef, authorization_context_key, LocalObjectAvailability, and LocalGitObjectAvailability from builtin_plugins/hosted_review/models.py into provider_resources/models.py with one implementation each, so core never imports a domain plugin (the observation-guarded local-availability helpers stay in hosted_review); the selected-ref service reports local object availability with those moved types; mb-s0gv later moves the remaining neutral records. ProviderPrincipal carries provider kind, instance, stable principal, optional visibility-partition digest, and the derived authorization-context key. At the single RepositoryObjectJobPort boundary, validate the AuthorizationContextRef mode and field combination, derive its key (never accept a caller-supplied key), map it once to that internal variant, and reject an invalid record before job lookup. Define GitFetchCredentialLease as an unforgeable process-local non-serializable handle into a core GitFetchCredentialLeaseRegistry in cache/jobs.py, separate from job identity. validate_git_fetch_credential_lease reads provider, instance, stable principal, authorization-context key, visibility partition, expiry, revocation, cancellation generation, and exact credential-free HTTPS sources from the registry entry, never from the handle, for every request before job lookup, including a request joining in-flight work. A provider-principal Git run uses the starting request's lease; if that request cancels or its lease is revoked, restart once under another attached live lease for an equal authorization-context key or fail the remaining requests typed. Leases authorize a context key, not a broker session. Prove the registry protocol with a test issuer. Until the Phase 3A askpass projection (mb-s123) exists, a provider-principal request with a valid lease fails with git_credentials_unavailable before Git starts, so no ambient credential can be used. selection.py performs no network work. Fetch directly into the store from a promisor remote recorded in the store's configuration snapshot, holding only the shared store lease (never an ordered lock) during network work and writing only job-private refs under refs/metabrowser/jobs/<job-id>/; verify the store configuration snapshot digest before spawning Git and refuse and request quarantine on mismatch; fetch change-request heads through the base repository's provider-published refs, never a fork URL; filter want lists to blob modes, bisect only per-object rejections up to the per-job cap, and mark the remainder deferred; then validate object format, expected OID, source, context kind, refspec, and generation, and publish with one update-ref --stdin compare-and-swap under the short repository-store lock that also deletes the job refs. Every lease and lock attempt uses its own open() of the lock file. Never mutate an attached checkout, create a worktree, expose store paths or secrets, or import provider schemas, gh, auth, catalog, chooser, and eviction into core.

## Notes

2026-09-22 (from mb-dg00, PR #226): this bead now owns the golden for an interruption during CAS ref publication. There is no CAS ref publication before publish_refs lands here in Phase 2B. Model it on tests/test_cli_cache_recovery_golden.py (SIGKILL at the publication boundary, then show the next run recovering). Also include recovery from a stale ref lock (see mb-2k9c).
