---
type: is
id: is-01m8hhrk32vnybr7hvjreszfhp
title: Preserve preexisting structured record grids during the additive validation
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-structured-data-views.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8hgz7pwbvvzkr2re1h7bwgn
hold: null
hold_until: null
created_at: 2026-11-28T17:03:06.848Z
updated_at: 2026-11-28T17:31:38.376Z
started_at: 2026-11-28T17:04:07.012Z
closed_at: 2026-11-28T17:31:38.375Z
close_reason: Restored the old value grid for bounded JSON5 record lists and benign YAML aliases, retaining exact-source diagnostics. Verified production startup with the collection plugin absent, 203 focused tests on the final combined head, exact hosted CI and macOS, and refreshed guided reviews.
resolution: null
duplicate_of: null
---
With the new Table default, bounded standalone JSON5 record lists and YAML lists with benign aliases need their preexisting value grid when exact source ranges are unavailable. Keep the optional collection plugin removable, and retain exact-parser diagnostics and guardrails.
