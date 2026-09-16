---
type: is
id: is-01m2mdsbr5x5z8tmyzy8h5rvdy
title: Reject non-portable values during artifact serialization
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:17:10.148Z
updated_at: 2026-09-16T07:13:34.261Z
closed_at: 2026-09-16T07:13:34.261Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable R8: serialize_artifact accepted NaN and integers beyond the JavaScript safe range, then emitted YAML that validate_artifact rejected. Validate emitted metadata through SoftSchema portable parsing before returning and add regression coverage.
