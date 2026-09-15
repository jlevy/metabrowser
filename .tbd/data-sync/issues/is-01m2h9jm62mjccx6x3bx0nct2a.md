---
type: is
id: is-01m2h9jm62mjccx6x3bx0nct2a
title: "Provider store kernel: auth-scoped snapshots, leases, and bounded reclamation"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-15T01:05:51.809Z
updated_at: 2026-09-15T01:31:31.626Z
---
Implement the provider-neutral store kernel before repository or PR snapshots: stable AuthorizationContextRef-scoped current pointers and validators, with volatile auth observations held only in Retrieval/v1; query-keyed index pointers; staged/committed/failed transaction state separate from collection coverage; immutable objects/manifests; current plus last-complete; reader leases; and entry-to-provider lock ordering with no network under lock. Refuse authenticated publication without a stable opaque principal ID. Retain current, last-complete, one diagnostic predecessor, and explicit archival pins regardless of availability; sweep older unreachable objects but never the last validated reachable observation. Test repeated observations for one principal, capability partition changes, reauthentication, fallback isolation, interruption, partial commit, concurrent refresh/read/reclaim, offline/deleted sources, and tombstone retention.
