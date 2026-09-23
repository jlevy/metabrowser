---
type: is
id: is-01m2h7jjga1ge5dzvs913n5fgs
title: "Plugin SDK: provider URL reducers for repository open targets"
kind: feature
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m2ktrc9jfznq2b0kh57e4735
  - type: blocks
    target: is-01m2kw2b66x74xxjjtdp3wrsr4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:30:52.937Z
updated_at: 2026-09-23T07:37:08.121Z
closed_at: 2026-09-23T07:37:08.118Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-bgs7 (URL open: HTTPS mirror, internal GitHub resolver, ref/path split, serving), with no public reducer SDK."
resolution: null
duplicate_of: null
---
Add a provider-neutral installed-plugin URL reducer registry. Each trusted reducer declares schemes and hosts and returns NotApplicable, Reduced, or terminal Rejected; core refuses reserved or overlapping claims before startup, requires exactly one owner, and never falls through after a claimed rejection. Reduced yields a credential-free Git source plus RepositorySelection. GitHub repository/tree/blob/commit/pull forms are the first consumer; reverse-order and overlap fixtures prove cache and CLI code never import or branch on GitHub.
