---
type: is
id: is-01m2mj2zrph9kmh788v80mv0d1
title: "Phase 0C.2 review R1: enforce the full browser parser result contract"
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
created_at: 2026-09-16T07:32:19.861Z
updated_at: 2026-09-16T07:32:34.739Z
---
The generic browser evidence harness accepts any object with a boolean ok field, so success or failure results can pass without the documented parsed value or error. Define the v1 BrowserParserSpec result contract in docs and require exactly ok true plus an object value for accepted records, or ok false plus a nonempty string error for rejected records. Add synthetic missing-value, missing-error, extra-field, and malformed-result regressions; keep unexpected parser throws as gate failures.
