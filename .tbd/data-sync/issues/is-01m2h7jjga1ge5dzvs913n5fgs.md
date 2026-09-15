---
type: is
id: is-01m2h7jjga1ge5dzvs913n5fgs
title: "Plugin SDK: provider URL reducers for repository open targets"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:30:52.937Z
updated_at: 2026-09-15T00:31:18.035Z
---
Add a provider-neutral installed-plugin registration point that reduces recognized hosted web URLs to an ordinary Git clone source plus RepositorySelection. Core owns validation, dispatch, ambiguity handling, and refusal; each provider plugin owns its hosts and path grammar. Only trusted installed Python plugins may register reducers; operator-directory plugins remain JavaScript-only. GitHub repository/tree/blob/commit/pull URL forms are the first consumer, and tests prove the generic cache never imports or branches on GitHub models.
