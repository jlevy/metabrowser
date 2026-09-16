---
type: is
id: is-01m2mja6bfq04nsza220t8yhsa
title: "Phase 0C.2 review R3: make document-case selection unambiguous"
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
created_at: 2026-09-16T07:36:15.981Z
updated_at: 2026-09-16T07:37:36.558Z
---
The Python corpus parser currently treats both an omitted record field and an explicit null record as a base_document case, while the generic Node harness selects only omitted record fields. This creates cross-runtime drift in case counts. Define document cases by an absent record field only, reject explicit null or other non-string record values in the Python gate, and add a regression proving both runtimes select the same cases.
