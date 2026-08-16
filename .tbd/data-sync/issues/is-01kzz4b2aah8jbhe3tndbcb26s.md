---
type: is
id: is-01kzz4b2aah8jbhe3tndbcb26s
title: Remove semantic file-type rollout compatibility aliases
kind: chore
status: open
priority: 3
version: 3
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - cleanup
  - file-types
dependencies: []
deferred_until: 2026-09-14T00:00:00Z
created_at: 2026-08-14T03:16:37.834Z
updated_at: 2026-08-16T08:05:43.471Z
extensions:
  linear:
    id: 8d0e5620-86bd-4caf-b82f-06ef9d2c66ca
    linked_at: 2026-08-16T08:05:43.471Z
---
After at least one supported release cycle, audit mixed-version compatibility and remove only aliases no longer needed: FILE_TYPE_TAXONOMY, legacy ROLLUP_FILE_TYPE_NAMED_LIMIT/RAW_LIMIT settings, type_top, type_tallies, and any old-browser fallback branches. Preserve saved raw extension filter tokens or migrate them explicitly. Confirm deployed browser assets cannot be cached across the removal, update the compatibility docs and release notes, and run the shared Python/browser conformance corpus before closing.
