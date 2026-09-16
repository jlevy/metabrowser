---
type: is
id: is-01m2mczntfwnj6n4w76mryy2t5
title: Keep public capability declarations off heavy registry imports
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
created_at: 2026-09-16T06:03:08.494Z
updated_at: 2026-09-16T07:13:34.191Z
closed_at: 2026-09-16T07:13:34.191Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent delivery review measured that plugin_api imports ArtifactContractSpec and CapabilitySet from artifact_contracts.py, making every import metabrowser and CLI command load frontmatter-format, jsonschema, and SoftSchema. Split dependency-light declaration dataclasses/type aliases into a public capability declarations module while keeping discovery, schema parsing, registry construction, and validation lazy/off ordinary startup.
