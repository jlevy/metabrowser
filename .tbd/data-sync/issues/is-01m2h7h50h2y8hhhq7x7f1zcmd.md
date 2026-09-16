---
type: is
id: is-01m2h7h50h2y8hhhq7x7f1zcmd
title: "GitHub Phase 3B: directly addressed PR bundle and selected refs"
kind: feature
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7hrjfx06hzpr7ptz7k9wn
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2kw2c5sak3agfksaqecefa5
parent_id: is-01m2h3vtmk6apasv27t6ygrrxf
hold: null
hold_until: null
created_at: 2026-09-15T00:30:06.351Z
updated_at: 2026-09-16T21:10:44.896Z
started_at: 2026-09-16T21:10:44.896Z
---
Hydrate one directly addressed PR without requiring an index. Publish one enforced ChangeRequest/v1 frontmatter artifact plus bounded distinct top-level ChangeRequestComment prose; Review/v1 frontmatter artifacts with and without optional summary bodies; ReviewThread/ReviewComment anchors; checks, status, retrieval, and manifest records under the active stable auth context. Ask core mb-jlon to fetch only selected base/head/optional merge refs. Preserve partial and not-found-under-context outcomes without tombstoning; expose immutable OIDs, current/last-complete fallback, and offline inspection through registered routes and a CLI golden.
