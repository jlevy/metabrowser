---
type: is
id: is-01kyjfkbmpv1sxeka2rcbazy70
title: Derive CLI mode/option metadata from one declarative table
kind: chore
status: open
priority: 3
version: 5
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-07-27T19:07:34.422Z
updated_at: 2026-11-20T19:15:57.888Z
extensions: {}
---
PR #14 review suggestion: _MODE_OPTIONS, _OPTION_LABELS, Typer declarations, and help panel grouping are parallel representations of option applicability and can drift (review findings R2/R3 were instances). Consider deriving the Typer options, applicability sets, display labels, and help panels from a single declarative mode/option definition in cli/main.py.
