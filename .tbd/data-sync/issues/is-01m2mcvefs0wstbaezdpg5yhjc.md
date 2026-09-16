---
type: is
id: is-01m2mcvefs0wstbaezdpg5yhjc
title: Reject unresolved and remote dynamic schema references at registry admission
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review:fable
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:00:49.904Z
updated_at: 2026-09-16T07:13:34.167Z
closed_at: 2026-09-16T07:13:34.167Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent registry review reproduced that registry admission accepts unresolved local refs and remote dynamicRef values. Validate the full self-contained schema graph at registry construction, reject all nonlocal reference mechanisms, and normalize validation failures so untrusted artifacts cannot trigger resolver, network, or error escapes.
