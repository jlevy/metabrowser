---
type: is
id: is-01m2mdkcn7gaavw041dd1q47d4
title: Parse installed schemas through SoftSchema portable YAML
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
created_at: 2026-09-16T06:13:54.470Z
updated_at: 2026-09-16T07:13:34.238Z
closed_at: 2026-09-16T07:13:34.238Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent registry review reproduced that schema admission still uses frontmatter_format.from_yaml_string and accepts YAML aliases or integers outside the cross-runtime safe range. Decode UTF-8 with leading BOM handling, parse schema text through SoftSchema's documented parse_yaml_text, normalize errors as CapabilityRegistryError, and add anchor and out-of-range schema admission regressions.
