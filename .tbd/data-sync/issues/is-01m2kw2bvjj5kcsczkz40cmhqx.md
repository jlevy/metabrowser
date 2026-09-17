---
type: is
id: is-01m2kw2bvjj5kcsczkz40cmhqx
title: "GitHub Phase 3A review: publish provider foundation PR"
kind: task
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kw2c5sak3agfksaqecefa5
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-16T01:07:30.801Z
updated_at: 2026-09-17T01:19:31.885Z
started_at: 2026-09-16T21:10:44.936Z
---
Independently review provider process, gh auth and transport, provider capability registry, repository-scoped neutral provider store, source bindings, attached-checkout activation, and HostedRepository publication. Resolve all findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 2B head. Prove multiple sources share one provider mirror, local checkouts are untouched, auth contexts are isolated, and metadata works before a Git store exists. Record exact stack and green CI; do not merge.
