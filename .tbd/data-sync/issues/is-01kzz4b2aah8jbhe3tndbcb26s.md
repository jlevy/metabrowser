---
type: is
id: is-01kzz4b2aah8jbhe3tndbcb26s
title: Remove semantic file-type rollout compatibility aliases
kind: chore
status: closed
priority: 3
version: 6
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - cleanup
  - file-types
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
deferred_until: 2026-09-14T00:00:00Z
created_at: 2026-08-14T03:16:37.834Z
updated_at: 2026-11-20T19:15:58.753Z
closed_at: 2026-11-01T16:21:22.974Z
close_reason: e66e21ab and 85695af1 removed the aliases; FILE_TYPE_TAXONOMY no longer appears in src on main.
resolution: null
duplicate_of: null
extensions: {}
---
After at least one supported release cycle, audit mixed-version compatibility and remove only aliases no longer needed: FILE_TYPE_TAXONOMY, legacy ROLLUP_FILE_TYPE_NAMED_LIMIT/RAW_LIMIT settings, type_top, type_tallies, and any old-browser fallback branches. Preserve saved raw extension filter tokens or migrate them explicitly. Confirm deployed browser assets cannot be cached across the removal, update the compatibility docs and release notes, and run the shared Python/browser conformance corpus before closing.
