---
type: is
id: is-01m2h9a5bd90k5yh2typvtrc2t
title: "PR #125 review D-R1: gate v0.11 implementation on the v0.10 release cut"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:14.475Z
updated_at: 2026-09-15T01:38:13.007Z
closed_at: 2026-09-15T01:38:13.005Z
close_reason: "Fixed D-R1: added mb-xxhi as the v0.10.0 release-from-main gate and made all v0.11 implementation roots depend on it; corrected release-candidate wording."
resolution: null
duplicate_of: null
---
PR #125 delivery D-R1. Create a release-start gate blocked by mb-i57d and make every independently runnable v0.11 implementation root depend on it, while leaving the design-review workflow ungated. Until the tag exists, describe v0.10 work as release-candidate code on main.
