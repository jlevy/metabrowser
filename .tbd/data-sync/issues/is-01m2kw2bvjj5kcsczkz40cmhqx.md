---
type: is
id: is-01m2kw2bvjj5kcsczkz40cmhqx
title: "GitHub Phase 3A review: publish provider foundation PR"
kind: task
status: closed
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2kw2c5sak3agfksaqecefa5
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-16T01:07:30.801Z
updated_at: 2026-09-23T07:37:15.772Z
started_at: 2026-09-16T21:10:44.936Z
closed_at: 2026-09-23T07:37:15.771Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-nkmq (PR data via gh runner and JSON records); the token broker, askpass bridge, provider snapshot store, adapter registry, binding and rebind are retired."
resolution: null
duplicate_of: null
---
Independently review provider process, gh auth and transport, the broker-pinned GitFetchCredentialLease and askpass bridge, provider capability registry, repository-scoped neutral provider store, source bindings, attached-checkout activation, and HostedRepository publication. Resolve all findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 2C head. Prove multiple sources share one provider mirror, local checkouts are untouched, auth contexts are isolated, provider-selected Git fetches use the same pinned principal with no ambient credential or configuration fallback, and metadata works before a Git store exists. Record exact stack and green CI; do not merge.
