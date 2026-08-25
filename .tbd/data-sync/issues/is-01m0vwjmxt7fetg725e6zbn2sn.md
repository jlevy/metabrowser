---
type: is
id: is-01m0vwjmxt7fetg725e6zbn2sn
title: "PR #74 review 74-13: restate ownership fitness tests as durable invariants"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:56.185Z
updated_at: 2026-08-25T07:59:01.171Z
closed_at: 2026-08-25T07:59:01.170Z
close_reason: "Fixed: ownership tests now assert durable architectural invariants with type-aware AST checks and actionable messages."
resolution: null
duplicate_of: null
---
Review 5406736360. tests/test_inventory_provider_ownership.py encodes legacy names without assertion messages. Keep the guards, express process-global-state and coordinator-only-open invariants, use type-aware analysis, and report offenders clearly.
