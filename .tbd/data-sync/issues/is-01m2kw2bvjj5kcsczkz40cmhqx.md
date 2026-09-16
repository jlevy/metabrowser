---
type: is
id: is-01m2kw2bvjj5kcsczkz40cmhqx
title: "GitHub Phase 3A review: publish provider foundation PR"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
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
updated_at: 2026-09-16T21:10:44.936Z
started_at: 2026-09-16T21:10:44.936Z
---
Independently review the provider process, gh auth and transport, provider capability registry, neutral provider-resource port and store, binding, and HostedRepository publication slice. Resolve all findings through the review shortcut, run make verify, and publish one formal draft GitHub PR with gh stacked on the exact green Phase 2B head. Record the exact PR URL, base and head branches and OIDs, review record, final green CI, and registration with mb-n2ro. Do not merge.
