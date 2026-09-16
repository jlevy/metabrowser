---
type: is
id: is-01m2ktpzzzg5crhj0ggx8bbt1t
title: "Hosted releases R1 implementation: oracle and GitHub normalization"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktq5v8236zvaxeyk7gzzhk
parent_id: is-01m2ktprcgghmr7z8mpshmymcd
created_at: 2026-09-16T00:43:49.630Z
updated_at: 2026-09-16T01:24:57.362Z
---
Implement Release R1 GitHub mapping: github/release_queries.py build_release_detail_request and build_release_assets_request use fixed bounded gh api inputs; github/release_mapping.py map_github_release, map_github_release_asset, and map_github_release_row normalize immediately to hosted_releases contracts. Add scrubbed detail, asset, and index-row fixtures plus test_github_release_coverage.py proving every field observed, derived, optional, or unavailable. R4 owns build_release_index_request and consumes the R1 row mapper. Keep raw payloads, credentials, and unbounded pagination out of durable state.
