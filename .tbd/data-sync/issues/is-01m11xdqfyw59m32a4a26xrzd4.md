---
type: is
id: is-01m11xdqfyw59m32a4a26xrzd4
title: "PR #31 review S2: record why /status/ departs from the URL grammar"
kind: bug
status: closed
priority: 4
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:10.141Z
updated_at: 2026-08-27T15:44:30.885Z
closed_at: 2026-08-27T15:44:30.884Z
close_reason: "Fixed in dbe3206: the /status/ grammar departure and its rationale are recorded in the plan, to be added to the grammar table when Phase 2 registers the route."
resolution: null
duplicate_of: null
---
docs/architecture.md:348 states the grammar as address space plus a path within it; /status/<scope>/<entry-id> substitutes an opaque digest. Record the departure when the route is registered.
