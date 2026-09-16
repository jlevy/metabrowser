---
type: is
id: is-01m2mcqnyg3602g4pat3rj5621
title: Preserve required null and empty values in generic artifact serialization
kind: bug
status: closed
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review:fable
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T05:58:46.479Z
updated_at: 2026-09-16T07:13:34.133Z
closed_at: 2026-09-16T07:13:34.133Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent Phase 0C.1 registry review reproduced that plugin_loader/artifact_contracts.py serialize_artifact uses frontmatter_format.to_yaml_string with its default value suppression. A valid ChangeRequest loses required comparison.merge_commit_oid: null and then fails validate_artifact. Serialize installed contract artifacts with suppress_vals=None and add a representative built-in frontmatter round-trip regression covering required null/empty values.

## Notes

Fable registry review reproduced the failure against a real ChangeRequest: generic YAML serialization dropped required null fields before parsing. Fix and regression are in progress.
