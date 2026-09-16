---
type: is
id: is-01m2m9vr7683jzj6ck2qmzkw07
title: "PR #134 review R5: enforce strict RFC 6901 pointers"
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
created_at: 2026-09-16T05:08:34.149Z
updated_at: 2026-09-16T05:09:07.693Z
closed_at: 2026-09-16T05:09:07.691Z
close_reason: "Fixed in 18ef513a: the evidence resolver enforces strict RFC 6901 escaping and canonical array indexes with invalid-pointer cases."
resolution: null
duplicate_of: null
---
PR #134 delegated review R5. tests/test_github_coverage.py: evidence pointers accepted noncanonical forms. Enforce RFC 6901 escaping and canonical array indexes with focused invalid cases.
