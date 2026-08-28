---
type: is
id: is-01m10xd666fefs5z7ft5m58zj0
title: "GitHub provider Phase 2: binding, acquisition, and snapshots"
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T06:09:37.988Z
updated_at: 2026-08-28T02:22:50.135Z
---
Add provider namespace and storage interfaces, immutable object snapshots, sync manifests, and atomic current resource sets. Bind a generic entry to a stable GitHub repository ID without changing cache identity. Map bounded REST or GraphQL responses into Phase 4 contracts with conditional requests, cursors, rate-limit and partial outcomes, tombstones, and credential-free retrieval metadata. Fetch selected repository, issue, PR, and provider refs on demand while preserving the last completed snapshot on failure.
