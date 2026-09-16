---
type: is
id: is-01m2mcv26wh1w19r9t77w7n0jw
title: Reject YAML aliases and enforce portable artifact parsing
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
created_at: 2026-09-16T06:00:37.332Z
updated_at: 2026-09-16T07:13:34.147Z
closed_at: 2026-09-16T07:13:34.147Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent registry review reproduced that generic artifact parsing accepts YAML anchors/aliases because it uses frontmatter_format.from_yaml_string rather than SoftSchema portable readers. Cached artifacts are untrusted and parsing must share SoftSchema BOM/fence/alias rules. Replace with a public portable reader and add valid/invalid vectors for frontmatter and pure YAML.
