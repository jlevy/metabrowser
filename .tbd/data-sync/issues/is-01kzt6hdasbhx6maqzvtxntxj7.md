---
type: is
id: is-01kzt6hdasbhx6maqzvtxntxj7
title: "Repository library Phase 6: measured large-repository acquisition"
kind: feature
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-12T05:18:50.711Z
updated_at: 2026-08-27T05:36:14.376Z
extensions:
  linear:
    id: 7766c0ab-8af4-4ee0-a3c5-d984d20cb1db
    linked_at: 2026-08-16T08:05:43.459Z
---
Only after measured repository sizes justify the additional state model, add shallow blobless acquisition plus progressive deepening. Expose and render truncated-history capability, disable blame while .git/shallow exists, and coordinate deepening with the unbounded-history session design. Preserve the ordinary full-history path as the default.
