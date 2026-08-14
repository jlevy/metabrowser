---
type: is
id: is-01kzz05x3x3d6y2n9gzeq8xmqg
title: Complete compatibility, cache, and migration boundaries
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - compatibility
  - migration
dependencies:
  - type: blocks
    target: is-01kzz0681weprsdjnd151fxkhj
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:03:54.364Z
updated_at: 2026-08-14T02:04:05.564Z
---
Define the additive transition for existing extensions, type_presets, type_families, canonical_extensions, ext_tallies, type_tallies, type_top, saved filter tokens, and mixed server/browser assets. Include registry schema/revision/fingerprint in affected inventory, response, and client cache identities; reject mismatched breakdowns safely; document intentional uppercase, dotfile, JSON Lines, and group-placement changes; and add explicit cleanup beads instead of deleting aliases in this rollout. Tests: old-client/new-server and new-client/old-server fallbacks, cache invalidation, saved filters, cold/live envelopes, and stable unchanged family IDs. Acceptance: the new model is additive for one supported cycle and semantic changes are documented rather than hidden.
