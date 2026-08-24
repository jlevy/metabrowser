---
type: is
id: is-01m0t65jjct33hrw3k3z2v74sf
title: Reconcile kebab-case assets and tree-first browser startup
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - browser
dependencies:
  - type: blocks
    target: is-01m0t65vgar07vys3fqmqnd0t5
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:28:04.682Z
updated_at: 2026-08-24T15:34:03.488Z
closed_at: 2026-08-24T15:34:03.487Z
close_reason: Audited all touched static references against PR 73 kebab-case renames, preserved the exact upstream tree-first/deferred-assets startup sequence, and kept app.js behavior identical to main apart from provider terminology; 111 focused naming/browser tests pass.
resolution: null
duplicate_of: null
---
Apply PR 73 static module renames everywhere touched by the refactor, including server.py asset URLs, plugin-sdk.js references, docs, fixtures, and browser tests. Preserve app.js tree-first load ordering, deferred shell tools, on-demand plugin assets, inline-tree reconciliation, event yielding, and renderer disposal behavior.
