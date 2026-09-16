---
type: is
id: is-01m2p1ps48qjh1qt3wmk8s63ra
title: "Repository library Phase 1A review: publish format-foundation PR"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - stack:publication
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.495Z
updated_at: 2026-09-16T21:24:54.516Z
started_at: 2026-09-16T21:24:54.515Z
---
Independently review the f01 application-home, source/store records, logical cache routes, lock order, atomic publication, migration refusal, security, distribution, CLI parity, and goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 0D head. Record exact stack evidence and final green CI. Do not merge.
