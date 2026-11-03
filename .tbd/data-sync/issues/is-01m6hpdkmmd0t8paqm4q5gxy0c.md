---
type: is
id: is-01m6hpdkmmd0t8paqm4q5gxy0c
title: Resume incomplete catalog backfill when cached display rows are already fresh
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:53:06.192Z
updated_at: 2026-11-03T21:53:28.737Z
started_at: 2026-11-03T21:53:28.736Z
---
Independent controller probe reopens a fresh incomplete catalog with500 cached Open rows: the UI reads five cached windows but issues no POST to resume all-repository metadata, leaving Catalog paused. Resume incomplete background backfill independently of whether the visible display target is already satisfied, while retaining failure retry windows, rate holds, disposal and request ownership. Recheck the unchanged resume-partial probe and complete/failure/rate-limit controls.
