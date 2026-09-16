---
type: is
id: is-01m2mdcqrdp312ddj4njbfp5m5
title: Enforce same-provider ownership for resource profiles and contracts
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review:fable
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:10:16.460Z
updated_at: 2026-09-16T07:13:34.224Z
closed_at: 2026-09-16T07:13:34.224Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent registry review reproduced that a capability provider with no contracts can register a resource profile over another provider's contract IDs, despite the architecture assigning a profile to the domain capability that owns its artifact contracts. Retain provider ownership or compare each profile against the same CapabilitySet's declared contract IDs; reject cross-provider profile claims and add a regression.
