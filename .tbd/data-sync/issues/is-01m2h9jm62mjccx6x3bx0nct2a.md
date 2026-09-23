---
type: is
id: is-01m2h9jm62mjccx6x3bx0nct2a
title: "Provider store kernel: auth-scoped snapshots, leases, and bounded reclamation"
kind: feature
status: closed
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-15T01:05:51.809Z
updated_at: 2026-09-23T07:37:14.676Z
started_at: 2026-09-16T21:10:44.880Z
closed_at: 2026-09-23T07:37:14.675Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-nkmq (PR data via gh runner and JSON records); the token broker, askpass bridge, provider snapshot store, adapter registry, binding and rebind are retired."
resolution: null
duplicate_of: null
---
Implement the provider-neutral store kernel behind ProviderResourceStorePort, keyed by stable RepositoryRef and then AuthorizationContextRef and logical target or query rather than a cache entry. Publish immutable objects and manifests, atomic current and last-complete pointers, explicit transaction, collection, and remote-consistency states, reader leases, diagnostic retention, and bounded reachability reclamation. Use repository-store then provider-resource lock order only when both are needed, with no network under lock. Test multiple sources sharing one repository, auth isolation, interruption, partial commit, concurrent refresh/read/reclaim, offline/deleted sources, and tombstone retention.
