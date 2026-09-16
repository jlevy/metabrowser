---
type: is
id: is-01m2mmgqnq6m6jmta0ekt0rxk7
title: "Phase 0C.2 review R14: permit complete cross-realm browser parser clones"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T08:14:47.478Z
updated_at: 2026-09-16T08:14:53.236Z
---
The restricted VM harness uses deep strict equality across host and VM realms, so a valid parser returning a complete shallow or deep clone can fail only because its object prototype belongs to another realm. Normalize or compare JSON-domain values type-sensitively without prototype identity, preferably while creating parser inputs inside the restricted realm to avoid capability leaks. Add shallow/deep clone passes plus record-loss and type-change failures.
