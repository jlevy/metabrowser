---
type: is
id: is-01m2m9vpk55mp82qshekzh75rk
title: "PR #134 review R2: align activity item IDs with corpus"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - review
  - stack:pr134
dependencies: []
parent_id: is-01m2m9twtnpsc6m809wfefrpr9
created_at: 2026-09-16T05:08:32.484Z
updated_at: 2026-09-16T05:09:06.521Z
closed_at: 2026-09-16T05:09:06.520Z
close_reason: "Fixed in 18ef513a: activity IDs now use change-request:<number>, and the recipe is executed against the portable repository-activity corpus."
resolution: null
duplicate_of: null
---
PR #134 delegated review R2. tests/fixtures/github/oracle/field-inventory.json: repository activity IDs used the full canonical change-request ID instead of repository-scoped change-request:<number>. Align the recipe with the portable repository-activity corpus and execute it in a test.
