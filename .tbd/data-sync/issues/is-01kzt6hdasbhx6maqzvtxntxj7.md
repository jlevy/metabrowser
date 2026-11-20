---
type: is
id: is-01kzt6hdasbhx6maqzvtxntxj7
title: "Repository library Phase 8: measured large-repository acquisition"
kind: feature
status: open
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-12T05:18:50.711Z
updated_at: 2026-11-20T19:15:58.670Z
extensions: {}
---
Only after measured repository sizes justify the additional state model, add shallow blobless acquisition plus progressive deepening. Expose and render truncated-history capability, disable blame while .git/shallow exists, and coordinate deepening with the unbounded-history session design. Preserve the ordinary full-history path as the default.

## Notes

2026-11-14 audit: v0.12's thin-mirror plan retired blobless clones for v1 (Retired From Earlier Plans): stores are full clones, with the repository size checked first and a clone that cannot finish inside the acquisition deadline refused with a typed state. This bead stays the place to revisit partial acquisition if measured repository sizes justify it.
