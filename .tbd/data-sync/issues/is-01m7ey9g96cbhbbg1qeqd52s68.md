---
type: is
id: is-01m7ey9g96cbhbbg1qeqd52s68
title: Watcher DefaultFilter hides changes under indexed node_modules and __pycache__
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:38.821Z
updated_at: 2026-11-20T17:01:50.831Z
closed_at: 2026-11-20T17:01:50.830Z
close_reason: Contained in mb-s0v3 (watcher DefaultFilter hides indexed paths); its detail is merged into mb-s0v3's notes
resolution: duplicate
duplicate_of: is-01m7kp7nppf4swardrp6c2gj8y
---
run_watcher (watch_backends.py) uses watchfiles' DefaultFilter, so changes under node_modules and __pycache__ are never delivered live even though the walker indexes those trees. Either filter consistently with the index or document the exclusion as intended.
