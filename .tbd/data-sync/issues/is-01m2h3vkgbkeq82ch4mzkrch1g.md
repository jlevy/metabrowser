---
type: is
id: is-01m2h3vkgbkeq82ch4mzkrch1g
title: "Repository library Phase 2B: provider jobs and selected refs"
kind: task
status: open
priority: 1
version: 24
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
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
updated_at: 2026-09-16T22:48:08.948Z
started_at: 2026-09-16T21:10:44.862Z
---
Extract provider-facing generic jobs over shared repository stores: per-store progress, coalescing, cancellation and stage outcomes; jobs.py-owned fetch_selected_ref and request_ref_fetch for bounded fetch of explicit refs into a Metabrowser namespace; and full-OID verification before ref publication. Key each job by store, source, closed FetchAuthorizationContext, fetch-policy version, and exact refspec; coalesce only exactly equal proven contexts and never coalesce unknown helper credentials. ProviderPrincipal carries provider kind, instance, stable principal, optional visibility-partition digest, and the exact canonical authorization-context key. At the single RepositoryObjectJobPort boundary, recompute and validate AuthorizationContextRef, map it once to that internal variant, and reject weaker or mismatched identity before job lookup. Define a process-local non-serializable GitFetchCredentialLease separately from job identity. The port accepts the matching context plus optional opaque lease; core validates full context, expiry, cancellation generation, and exact credential-free HTTPS source before staging. ProviderPrincipal work without a valid lease fails closed and never falls back to ambient Git helpers or SSH agents. Phase 2B defines and tests this generic boundary; the GitHub broker and one-shot askpass projection arrive in Phase 3A. selection.py performs no network work. Stage with no lock, then validate object format, expected OID, source, context kind, refspec, and generation before repository-store CAS publication. Never mutate an attached checkout, create a worktree, expose store paths or secrets, or import provider schemas, gh, auth, catalog, chooser, and eviction into core.
