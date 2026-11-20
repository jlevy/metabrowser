---
type: is
id: is-01m7kp7nppf4swardrp6c2gj8y
title: Python watcher misses .gitignore edits and changes under DefaultFilter paths (R7, D3, D4)
kind: bug
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7r5gs472n9g927516cpk
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:02.389Z
updated_at: 2026-11-20T17:01:32.203Z
---
The watcher drops hidden names, so .gitignore edits never reclassify entries, and watchfiles DefaultFilter hides node_modules, .venv, and __pycache__ changes that the walker indexes. Observe the whole admitted scope; overflow and retry are mb-pn95 and mb-dwo6; delete the unused INVENTORY_REFRESH_TTL_S. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md.

## Notes

2026-11-20 audit: absorbs mb-xr2g (found by the documentation rewrite, closed as a duplicate): run_watcher in watch_backends.py uses watchfiles' DefaultFilter, so changes under node_modules and __pycache__ are never delivered live although the walker indexes those trees. Either filter consistently with the index or document the exclusion as intended.
