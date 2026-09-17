---
type: is
id: is-01m1389aetecehg10qdf7zb9rz
title: "Cache state routes: layout, sources, and repository stores"
kind: feature
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m1389rewn2mkj8emj3wxwpr7
  - type: blocks
    target: is-01m2p1ps48qjh1qt3wmk8s63ra
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-28T03:58:14.488Z
updated_at: 2026-09-17T21:29:33.526Z
started_at: 2026-09-16T21:24:52.524Z
closed_at: 2026-09-17T21:29:33.524Z
close_reason: "Implemented read-only /api/cache/layout, /api/cache/sources, /api/cache/source/{slug}, and /api/cache/stores projecting Phase 1A logical records through metab --api, with parity rows and the cli-api-cache golden (12 cases: missing home, empty cache, aliased stores, quarantine, reclamation, future-format and shared-home refusals). Per-request lazy home resolution that never creates the home or takes a lock; read paths never repair and report typed path-free problems; keyset pagination with a measured per-request record budget (DEFAULT_PAGE_LIMIT 25, MAX_PAGE_LIMIT 100, MAX_RECORDS_PER_REQUEST 400); no path, pack name, Git internal, or object count in any response. Published in PR #140 at 18ec8870 with full green CI."
resolution: null
duplicate_of: null
---
Add read-only routes that project Phase 1A logical records: /api/cache/layout, /api/cache/sources, /api/cache/source/{slug}, and /api/cache/stores. These satisfy the persisted-state clause through metab --api, not a bespoke inspection command. Report source/store identity, alias generation, publication state, and reclamation outcomes; never expose cache filesystem paths, pack filenames, Git internals, or unstable object counts.
