---
type: is
id: is-01m2mcv370ebwe5q8vkrwrm9x8
title: Verify compiled schema digest against schema content
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
created_at: 2026-09-16T06:00:38.367Z
updated_at: 2026-09-16T07:13:34.181Z
closed_at: 2026-09-16T07:13:34.181Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent registry review reproduced that registry admission only compares the declared digest with x-softschema.schema_sha256 and does not recompute it; tampered schema content with the old digest is accepted. Use a public SoftSchema content-digest verifier or first-party upstream API and add a tampered-schema regression.
