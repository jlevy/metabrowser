---
type: is
id: is-01m2mefkfhmae4yypfyg4h3h0g
title: Make v1 contract evidence self-resolving
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
created_at: 2026-09-16T06:29:18.952Z
updated_at: 2026-09-16T07:13:34.375Z
closed_at: 2026-09-16T07:13:34.375Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable R17: ArtifactContractSpec exposed only opaque corpus and browser-parser IDs, so a generic installed-distribution evidence gate could not resolve third-party packages without hard-coded Metabrowser paths. Add immutable packaged corpus and browser parser module evidence with exact digests, update the browser conformance harness to consume those handles, and document the later runtime plugin binding.
