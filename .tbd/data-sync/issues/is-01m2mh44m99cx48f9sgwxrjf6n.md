---
type: is
id: is-01m2mh44m99cx48f9sgwxrjf6n
title: "Phase 0C.2 architecture: register format inventory and parity evidence"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - docs
dependencies: []
parent_id: is-01m2krxqqcrn84sje77js6e1vx
created_at: 2026-09-16T07:15:29.031Z
updated_at: 2026-09-16T08:43:20.280Z
closed_at: 2026-09-16T08:43:20.280Z
close_reason: "Implemented, verified, and published in green draft PR #136 at b907bb2734929cd0858207ba5d73639aee168636."
resolution: null
duplicate_of: null
---
Update the hosted-resource architecture map, plugin documentation, active plan, changelog, and parity evidence so every installed contract/profile has one maintained registered row and named checker, while leaving all unimplemented routes, kinds, views, cache paths, and provider adapters planned. Add focused docs/parity tests that fail when installed declarations and the maintained inventory diverge; follow the architecture-document status/check conventions and common-doc footer.

## Notes

Registered all 16 installed artifact contracts and both resource profiles in the maintained architecture inventory; named devtools/check_artifact_contracts.py as the executable maintainer; updated plugin and CLI guidance, architecture status/map, active phase plan, changelog, and docs-discipline coverage. Kept cache, provider, network, route, kind, view, manifest, and static-asset surfaces explicitly unimplemented. Validation: artifact checker 16 contracts and 2 profiles; 23 focused tests; parity 26 covered routes plus 5 exemptions, 9 kinds, and 29 functional aspects; Flowmark, Ruff, public hygiene, and git diff check green.
