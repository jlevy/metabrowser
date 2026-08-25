---
type: is
id: is-01m0vdp6nft0d8m9ayf6kq5swq
title: "PR #74 review R7: rename Python provider module clearly"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:44.013Z
updated_at: 2026-08-25T04:46:36.440Z
closed_at: 2026-08-25T04:46:36.438Z
close_reason: R7 resolved and verified by make verify.
resolution: null
duplicate_of: null
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R7 Low. Rename providers/python.py to providers/python_inventory.py, update imports, loggers, tests, ownership checks, and maintained docs directly, remove current InventoryIndex aliases and touched decorative banners, and add no compatibility shim.

## Notes

Renamed providers/python.py directly to providers/python_inventory.py with no compatibility shim. Updated imports, logger names, source checks, ownership checks, maintained architecture/spec/research docs, and CHANGELOG. Removed InventoryIndex test aliases and touched decorative comment banners.
