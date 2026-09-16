---
type: is
id: is-01m1389aetecehg10qdf7zb9rz
title: "Cache state routes: layout, sources, and repository stores"
kind: feature
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: null
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
updated_at: 2026-09-16T21:27:30.283Z
started_at: 2026-09-16T21:24:52.524Z
---
Add read-only routes that project Phase 1A logical records: /api/cache/layout, /api/cache/sources, /api/cache/source/{slug}, and /api/cache/stores. These satisfy the persisted-state clause through metab --api, not a bespoke inspection command. Report source/store identity, alias generation, publication state, and reclamation outcomes; never expose cache filesystem paths, pack filenames, Git internals, or unstable object counts.
