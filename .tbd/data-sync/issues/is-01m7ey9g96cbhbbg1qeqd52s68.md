---
type: is
id: is-01m7ey9g96cbhbbg1qeqd52s68
title: Watcher DefaultFilter hides changes under indexed node_modules and __pycache__
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:38.821Z
updated_at: 2026-11-15T06:28:38.821Z
---
run_watcher (watch_backends.py) uses watchfiles' DefaultFilter, so changes under node_modules and __pycache__ are never delivered live even though the walker indexes those trees. Either filter consistently with the index or document the exclusion as intended.
