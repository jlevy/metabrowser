---
type: is
id: is-01kzwkwgrrdww56y99n5gsz65c
title: Add strict browser lifecycle primitives
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-12-directory-file-type-summary.md
labels:
  - frontend
dependencies:
  - type: blocks
    target: is-01kzwkwvt6ppnxg0m5snmps1eb
  - type: blocks
    target: is-01kzwkx7fnx68rfsx0d6y36w1w
  - type: blocks
    target: is-01kzwkxst27f1wrrq2ktft2jmy
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:50:35.030Z
updated_at: 2026-08-13T03:51:17.056Z
---
Implement request_error.js, formatters.js, inventory_scope.js, contribution_registry.js, resource_context.js, view_state.js, exact types.d.ts additions, thin plugin_sdk.js adapters, and minimal app.js integration from the Strict Browser-Core Function Map. Preserve existing SDK defaults and spec.dispose while adding per-instance handles. Prove multiplexed context refresh, active gating, abort/late-completion safety, dynamic print state, formatter parity, duplicate registry rejection, and exactly-once cleanup with strict check-JS and DOM tests; do not expand the legacy allowlist.
