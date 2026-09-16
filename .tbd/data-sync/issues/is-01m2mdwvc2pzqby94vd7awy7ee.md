---
type: is
id: is-01m2mdwvc2pzqby94vd7awy7ee
title: Reject malformed mutable capability-set declarations
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:19:04.448Z
updated_at: 2026-09-16T07:13:34.276Z
closed_at: 2026-09-16T07:13:34.276Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable R9: CapabilitySet tuple annotations are not runtime-enforced, so None/list declarations can raise raw TypeError or violate immutable snapshot semantics. Normalize malformed capability sets to CapabilityRegistryError and test build/doctor paths.
