---
type: is
id: is-01m2ktrc9jfznq2b0kh57e4735
title: "Hosted releases R2 implementation: direct URL acquisition and publication"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktrgz0vvvg0z0ggf17yjrb
parent_id: is-01m2ktr3rq01pq9w0dpbvm1vpy
created_at: 2026-09-16T00:44:34.990Z
updated_at: 2026-11-14T18:46:09.775Z
closed_at: 2026-11-14T18:46:09.774Z
close_reason: "Obsolete as written: the R2 implementation targets ProviderResourceStorePort, format_hosted_address and reduce_github_url, none of which exist on main after #246 (kept only on draft #247)."
resolution: canceled
duplicate_of: null
---
Implement Release R2 direct cache: github/urls.py reduce_github_url and parse_github_release_selection reduce release/tag URLs to typed RepositorySelection locators; hosted_releases/service.py get_release and refresh_release resolve stable provider object IDs and publish through ProviderResourceStorePort; plugin_loader/provider_addresses.py format_hosted_address creates the canonical release address. Use bounded 0..N asset metadata with declared maximum and explicit partial/truncation evidence, exact observed tag OIDs, auth-scoped current/last-complete pointers, offline reuse, and no asset-byte fetching by implication. Add routes/CLI cache goldens and failure fixtures.
