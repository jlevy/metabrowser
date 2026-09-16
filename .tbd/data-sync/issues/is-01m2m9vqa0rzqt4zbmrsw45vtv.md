---
type: is
id: is-01m2m9vqa0rzqt4zbmrsw45vtv
title: "PR #134 review R3: make schema captures exact"
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
created_at: 2026-09-16T05:08:33.215Z
updated_at: 2026-09-16T05:09:06.872Z
closed_at: 2026-09-16T05:09:06.871Z
close_reason: "Fixed in 18ef513a: GraphQL schema evidence is split by exact request and tests pin exact roots, reduced shapes, and introspection field lists."
resolution: null
duplicate_of: null
---
PR #134 delegated review R3. tests/test_github_coverage.py and tests/fixtures/github/oracle/schema-nullability-*.json: split schema captures by request and assert exact root aliases, reduced response shapes, and introspection field-name lists.
