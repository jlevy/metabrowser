---
type: is
id: is-01m2mebbwwzba6k4r0ryrjd46s
title: Verify installed logical schema digests independently
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:27:00.123Z
updated_at: 2026-09-16T07:13:34.357Z
closed_at: 2026-09-16T07:13:34.357Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable R16: registry admission compared only the provider-declared logical digest with the embedded schema digest, so a provider could mutate schema content, recompute the byte hash, and retain a stale logical identity. Recompute SoftSchema's documented canonical structural digest at admission and add a mutation regression.
