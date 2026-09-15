---
type: is
id: is-01m2k1jkq9cvxx9db7a0z14b0z
title: "Hosted review Phase 0B.2: complete review, signal, and activity records"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jnf5t6bgg340skd537hn
  - type: blocks
    target: is-01m2k1jq7ydswdag1x08n30hvn
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:31.585Z
updated_at: 2026-09-15T17:24:35.192Z
---
Extend models.py, artifacts.py, and the shared corpus with ChangeRequestComment, Review with optional Markdown summary, ReviewThread, ReviewComment, tagged file/line/range ReviewAnchor, Check, CommitStatus, and RepositoryActivity. Validate bounded relationships to ChangeRequest, comparison and revision identities, explicit unavailable or unresolved anchors, body and no-body reviews, unknown enums, and closed objects with no raw payload or extension bag.
