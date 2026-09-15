---
type: is
id: is-01m2h7jjgpzyfbf10238j32z6q
title: "Hosted review Phase 4B: Pull Requests virtual nav collection"
kind: feature
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-15T00:30:52.949Z
updated_at: 2026-09-15T00:30:52.949Z
---
Add the Pull Requests repository-scoped nav panel after direct PR viewing and the bounded index ship. Project ChangeRequestIndex rows through RepositoryActivity/v1 and reuse Git history paging, virtualization, roving selection, restoration, loading/error/disposal, and item-like/folder-like mechanics through the public plugin SDK. Selecting a row opens the direct PR document; expanding it exposes comparison file children. Counts, grouping, and visibility come from the bounded model rather than mounted DOM rows.
