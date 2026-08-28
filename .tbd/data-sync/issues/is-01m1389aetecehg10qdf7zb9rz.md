---
type: is
id: is-01m1389aetecehg10qdf7zb9rz
title: "Cache state routes: /api/cache/layout, entries, and entry"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels: []
dependencies:
  - type: blocks
    target: is-01m1389rewn2mkj8emj3wxwpr7
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-28T03:58:14.488Z
updated_at: 2026-08-28T03:58:28.818Z
---
Add three read-only routes projecting the Phase 1A records: /api/cache/layout (format version, home, directories), /api/cache/entries (identity, publication state, head revision per entry), and /api/cache/entry/{slug}. These satisfy the state clause: cache layout, entry identity, entry state, and reclamation outcomes are read as normalized models through --api like any other surface, not through a bespoke inspection command. Project logical state only; never a directory listing, because pack file names and .git internals are not stable across runs.
