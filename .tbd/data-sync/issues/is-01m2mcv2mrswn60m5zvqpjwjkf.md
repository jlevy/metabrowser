---
type: is
id: is-01m2mcv2mrswn60m5zvqpjwjkf
title: Apply SoftSchema enforced closure in generic record validation
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
created_at: 2026-09-16T06:00:37.783Z
updated_at: 2026-09-16T07:13:34.156Z
closed_at: 2026-09-16T07:13:34.156Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent registry review reproduced that plugin_loader validate_record uses raw Draft202012Validator and accepts undeclared properties when a contributed schema omits additionalProperties. Use SoftSchema enforced structural validation/preparation rather than raw JSON Schema validation and add an open-schema regression.
