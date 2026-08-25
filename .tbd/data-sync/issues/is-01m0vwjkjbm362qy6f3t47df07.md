---
type: is
id: is-01m0vwjkjbm362qy6f3t47df07
title: "PR #74 review 74-11: centralize provider resolution"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:54.792Z
updated_at: 2026-08-25T07:18:54.792Z
---
Review 5406736360. factory.py and runtime.py have three normalization/error paths. Normalize and validate in create_inventory_backend, route settings/runtime through it, and use typing.assert_never for the closed provider enum.
