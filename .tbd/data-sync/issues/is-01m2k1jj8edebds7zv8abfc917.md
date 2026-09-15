---
type: is
id: is-01m2k1jj8edebds7zv8abfc917
title: "Hosted review Phase 0B.1: complete provider storage and repository records"
kind: task
status: open
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jkq9cvxx9db7a0z14b0z
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2kb2nga7qt6kw5a07s2x7m1
  - is-01m2kb31dhpy38zhaf2f42b71r
  - is-01m2kb3g6wktd1ns9zhdcqk6d9
  - is-01m2kb410hgwb52hxrvxfnwc65
  - is-01m2kb4fa0swgkhrvw3qq21gtq
  - is-01m2kb505pj16mgj8secgn4dex
  - is-01m2kb5g8pf551djgfmf9kcm87
  - is-01m2kb6031dk9t2pzt5d35fvyd
created_at: 2026-09-15T17:24:30.089Z
updated_at: 2026-09-15T20:12:53.217Z
---
Complete the provider-neutral, no-network storage/repository/index record family through eight reviewable child beads: freeze namespace and publication semantics; keep Python/JavaScript provider namespace scalars aligned; add AuthorizationContextRef and Retrieval; add ResourceSet, ProviderSyncManifest, and Tombstone; add auth-independent ProviderBinding and HostedRepository identity; add query-keyed ChangeRequestIndex; package portable corpora; then run independent reviews, full verification, and publish the formal stack. No provider acquisition, filesystem store, route, view, manifest registration, or new dependency. Phase 0C owns compiled SoftSchema and full browser parsers for the new records.

## Notes

Refined after independent architecture and contract reviews. Key decisions still owned by mb-tznv: index volatility belongs in manifest retrieval evidence, ResourceSet/current/last-complete roles need one authority, provider namespace inputs require canonical ASCII spelling, tombstone corroboration must be measurable, and query/auth digests require canonical JSON projections. The child sequence is blocked on mb-n2ro landing Phase 0A.
