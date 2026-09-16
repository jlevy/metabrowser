---
type: is
id: is-01m2mk1ke5hfv4pzj4ytr28ma9
title: "Phase 0C.2 review R6: model browser consumption explicitly"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:03.044Z
updated_at: 2026-09-16T08:39:43.426Z
closed_at: 2026-09-16T08:39:43.426Z
close_reason: "Fixed in b907bb2734929cd0858207ba5d73639aee168636 and formally disposed on PR #136: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401"
resolution: null
duplicate_of: null
---
Artifact contracts expose opaque consumer IDs and an optional browser parser, so the generic gate cannot require parser evidence when a contract is browser-consumed. Add a provider-neutral typed consumption role or equivalent explicit declaration, reject browser-consumed contracts without parser evidence, preserve genuinely server-only contracts, update inventories/docs/tests, and avoid provider-name heuristics.

## Notes

Implemented explicit provider-neutral ArtifactContractSpec.browser_consumed boolean. Registry admission now requires BrowserParserSpec exactly when browser_consumed is true, rejects parser evidence on server-only declarations, and validates a real bool. All 16 built-in contracts declare the role explicitly; public plugin docs, durable architecture/plan, changelog, installed inventory, and focused API/registry/contract tests reflect the invariant without consumer-name heuristics. Integrated focused suite: 103 passed; Ruff, BasedPyright, Biome, Flowmark, and installed artifact inventory gate pass. Leave in_progress until PR disposition.
