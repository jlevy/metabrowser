---
type: is
id: is-01m2kvemzp183vrykz849c0s5a
title: "Provider resources: neutral artifact publication and cache port"
kind: feature
status: in_progress
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - provider-resources
dependencies:
  - type: blocks
    target: is-01m2ktnwpapx26rybv4w3pbshk
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-16T00:56:44.789Z
updated_at: 2026-09-17T01:36:44.484Z
started_at: 2026-09-16T21:10:44.871Z
---
Before provider storage becomes durable, move content-neutral provider identity and publication ownership from hosted_review into provider_resources. Incorporate the reviewed Phase 0D source-based ProviderBinding and separate local Git object availability. Define ProviderResourceStorePort with repository-scoped stage, publish, current/last-complete, lease, and reclaim methods; inject it through trusted lifecycle registration without exposing paths. Keep domain records and views in domain plugins. Prove unrelated plugin families and multiple source attachments reuse one stable provider repository.
