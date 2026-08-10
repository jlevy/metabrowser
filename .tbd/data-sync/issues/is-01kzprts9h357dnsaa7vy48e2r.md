---
type: is
id: is-01kzprts9h357dnsaa7vy48e2r
title: Live filter is not a recency window and reads as broken
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T21:21:34.512Z
updated_at: 2026-08-10T21:21:34.512Z
---
active_tracker._is_trackable only admits BROWSER_TRACKABLE_EXTS files under /.logs/ or /.state/, so Live answers 'which run artifact is being appended right now', not 'what changed recently'. On a repo without agent run logs it is structurally empty, sitting next to Past hour on an axis it does not belong to. The folder-pruning bug is fixed and the empty state now explains itself; what remains is whether to move it off the age menu and name it for what it tracks.
