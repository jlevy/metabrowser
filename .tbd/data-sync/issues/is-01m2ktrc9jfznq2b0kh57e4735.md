---
type: is
id: is-01m2ktrc9jfznq2b0kh57e4735
title: "Hosted releases R2 implementation: direct URL acquisition and publication"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktrgz0vvvg0z0ggf17yjrb
parent_id: is-01m2ktr3rq01pq9w0dpbvm1vpy
created_at: 2026-09-16T00:44:34.990Z
updated_at: 2026-09-16T01:24:57.611Z
---
Implement Release R2 direct cache: github/urls.py reduce_github_url and parse_github_release_selection reduce release/tag URLs to typed RepositorySelection locators; hosted_releases/service.py get_release and refresh_release resolve stable provider object IDs and publish through ProviderResourceStorePort; plugin_loader/provider_addresses.py format_hosted_address creates the canonical release address. Use bounded 0..N asset metadata with declared maximum and explicit partial/truncation evidence, exact observed tag OIDs, auth-scoped current/last-complete pointers, offline reuse, and no asset-byte fetching by implication. Add routes/CLI cache goldens and failure fixtures.
