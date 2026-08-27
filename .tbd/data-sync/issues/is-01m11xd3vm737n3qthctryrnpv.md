---
type: is
id: is-01m11xd3vm737n3qthctryrnpv
title: "PR #31 review R5: Phase 4 freezes the GitHub model with no coverage oracle"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:28:50.035Z
updated_at: 2026-08-27T15:44:27.376Z
closed_at: 2026-08-27T15:44:27.375Z
close_reason: "Fixed in dbe3206: Phase 4 gains a scrubbed recorded-response coverage oracle with a single check, and the GraphQL-only field presumption is stated in both the model section and the deferred-decisions list."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:583,808,942. review_decision and counts.reviews are GraphQL-only while Phase 5 claims transport is undecided; ~16 contracts frozen with no recorded real responses.
