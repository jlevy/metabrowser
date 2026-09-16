---
type: is
id: is-01m2mk1ke5hfv4pzj4ytr28ma9
title: "Phase 0C.2 review R6: model browser consumption explicitly"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:03.044Z
updated_at: 2026-09-16T08:01:52.828Z
---
Artifact contracts expose opaque consumer IDs and an optional browser parser, so the generic gate cannot require parser evidence when a contract is browser-consumed. Add a provider-neutral typed consumption role or equivalent explicit declaration, reject browser-consumed contracts without parser evidence, preserve genuinely server-only contracts, update inventories/docs/tests, and avoid provider-name heuristics.

## Notes

Implemented explicit provider-neutral ArtifactContractSpec.browser_consumed boolean. Registry admission now requires BrowserParserSpec exactly when browser_consumed is true, rejects parser evidence on server-only declarations, and validates a real bool. All 16 built-in contracts declare the role explicitly; public plugin docs, durable architecture/plan, changelog, installed inventory, and focused API/registry/contract tests reflect the invariant without consumer-name heuristics. Integrated focused suite: 103 passed; Ruff, BasedPyright, Biome, Flowmark, and installed artifact inventory gate pass. Leave in_progress until PR disposition.
