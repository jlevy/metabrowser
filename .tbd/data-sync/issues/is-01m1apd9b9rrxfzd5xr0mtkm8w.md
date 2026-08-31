---
type: is
id: is-01m1apd9b9rrxfzd5xr0mtkm8w
title: "PR #89 F1: local-origin decision contradicted twice in the same plan"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1apd8ye0cvejxessb3ppzjy
created_at: 2026-08-31T01:19:45.512Z
updated_at: 2026-08-31T01:40:12.528Z
closed_at: 2026-08-31T01:40:12.527Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #89."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md Non-Goals (:118-119) still says local transport overrides remain disabled, and Testing Strategy (:1105-1106) still specifies the test-only escape hatch the closed decision says it rejected. Verified: both passages present and contradictory.
