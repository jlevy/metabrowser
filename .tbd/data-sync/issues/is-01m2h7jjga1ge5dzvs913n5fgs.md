---
type: is
id: is-01m2h7jjga1ge5dzvs913n5fgs
title: "Plugin SDK: provider URL reducers for repository open targets"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:30:52.937Z
updated_at: 2026-09-15T01:19:44.590Z
---
Add a provider-neutral installed-plugin URL reducer registry. Each trusted reducer declares schemes and hosts and returns NotApplicable, Reduced, or terminal Rejected; core refuses reserved or overlapping claims before startup, requires exactly one owner, and never falls through after a claimed rejection. Reduced yields a credential-free Git source plus RepositorySelection. GitHub repository/tree/blob/commit/pull forms are the first consumer; reverse-order and overlap fixtures prove cache and CLI code never import or branch on GitHub.
