---
type: is
id: is-01m0vwjkjbm362qy6f3t47df07
title: "PR #74 review 74-11: centralize provider resolution"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:54.792Z
updated_at: 2026-08-25T07:59:00.543Z
closed_at: 2026-08-25T07:59:00.543Z
close_reason: "Fixed: provider spelling normalization and validation live only in the sealed factory."
resolution: null
duplicate_of: null
---
Review 5406736360. factory.py and runtime.py have three normalization/error paths. Normalize and validate in create_inventory_backend, route settings/runtime through it, and use typing.assert_never for the closed provider enum.
