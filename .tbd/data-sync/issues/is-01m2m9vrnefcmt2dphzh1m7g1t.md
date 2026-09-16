---
type: is
id: is-01m2m9vrnefcmt2dphzh1m7g1t
title: "PR #134 review R6: normalize check parent and revision evidence"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - review
  - stack:pr134
dependencies: []
parent_id: is-01m2m9twtnpsc6m809wfefrpr9
created_at: 2026-09-16T05:08:34.605Z
updated_at: 2026-09-16T05:09:08.153Z
closed_at: 2026-09-16T05:09:08.150Z
close_reason: "Fixed in 18ef513a: check parent resolution requires an exactly-one numeric database-ID join to the suite node ID and asserts equal suite/run head SHAs."
resolution: null
duplicate_of: null
---
PR #134 delegated review R6. tests/fixtures/github/oracle/field-inventory.json and tests/test_github_coverage.py: require an exactly-one numeric suite database-ID join to the normalized suite node ID and assert suite/run head revision equality.
