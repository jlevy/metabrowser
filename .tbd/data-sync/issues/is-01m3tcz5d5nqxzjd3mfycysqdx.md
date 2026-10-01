---
type: is
id: is-01m3tcz5d5nqxzjd3mfycysqdx
title: A served commit the mirror lacks shows 'Could not load this commit.' instead of the fetch state
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T00:14:00.099Z
updated_at: 2026-10-01T00:14:00.099Z
---
QA record (rerun on #243): navigating a served page to /commit/<oid> for a commit the mirror lacks shows 'Could not load this commit.' It was not checked whether this predates #243. Compare the /view/ selection_state pending/fetch_failed path ('Address not fetched').
