---
type: is
id: is-01m2mbre2bk9m00vd3h3e59p2p
title: "Phase 0C.1 review R1: reject lone surrogates in browser model strings"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T05:41:42.601Z
updated_at: 2026-09-16T07:13:34.088Z
closed_at: 2026-09-16T07:13:34.086Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable High: hosted-review browser nonemptyString/nullableString accept lone UTF-16 surrogates while Pydantic rejects them. Add a shared no-allocation Unicode-scalar check to both string helpers and portable invalid cases for ordinary text and a query-key input so Python/browser parity covers both paths. Finding applies to current Phase 0C.1 branch.
