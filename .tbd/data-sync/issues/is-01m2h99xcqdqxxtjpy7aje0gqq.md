---
type: is
id: is-01m2h99xcqdqxxtjpy7aje0gqq
title: "PR #125 review C-R2: separate transaction state from collection coverage"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:06.326Z
updated_at: 2026-09-15T01:38:07.718Z
closed_at: 2026-09-15T01:38:07.716Z
close_reason: "Fixed C-R2: separated transaction state from per-collection coverage, allowed honest committed partial current observations, preserved last-complete, and kept failed/invalid acquisitions from moving pointers."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R2. Model staged, committed, and failed acquisition separately from not_requested, partial, complete, and unavailable resource coverage. Define GraphQL data plus errors, null nodes, REST page failures, truncation, and current-pointer publication fixtures.
