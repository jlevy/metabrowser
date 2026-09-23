---
type: is
id: is-01m35sjt41tv1vzam373bgdrdd
title: Review v0.12 stack readiness and publish executable alpha test plan
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
hold: null
hold_until: null
created_at: 2026-09-23T00:10:23.729Z
updated_at: 2026-09-23T00:58:01.063Z
started_at: 2026-09-23T00:10:43.003Z
closed_at: 2026-09-23T00:58:01.062Z
close_reason: "Published reviewed alpha test plan/status reconciliation in PR #225 atop Stack 218; exact head ff94e367, full local verify and all seven CI checks passed. Full top-level review and per-layer delta reviews posted; beads/specs/PR descriptions and landing dependencies reconciled. Future implementation, bug fixes, alpha acceptance and landing remain separately open."
resolution: null
duplicate_of: null
---
Audit current GitHub review coverage, stack organization, designs, and remaining work for URL/Git/GitHub PR alpha testing. Add an end-to-end manual and automated test plan as a new PR above #216; publish review findings on GitHub. Preserve existing PR heads and local work.

## Notes

2026-09-22 completed review/publication: https://github.com/jlevy/metabrowser/pull/225 is the ready-for-review eighth layer of Stack 218, head ff94e3676bf0f7caab7a8bdfdbb18eb8b1f8e1c9 over #216 b3c001a96eed64eb77961c2b7165b103af98b77c. The original seven heads and exact chain are unchanged. All seven CI checks passed: https://github.com/jlevy/metabrowser/actions/runs/35803858717 . Local make verify passed (3112 pytest tests, two skips, 147 CLI transcript checks, dependency audits and installed-wheel/distribution checks); pre-push gate passed. Real unmodified Git 2.50.1 CLI T0 smoke passed for cold/warm acquisition, nested Markdown/JSON/tree/progress, origin-absent reuse, and local filesystem inspection. Independent Astra plan review found no actionable plan blocker: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787107670 . Full top-level review: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 . #136/#139 later functional deltas received independent technical review; #217/#216 acceptance remains open. New finding mb-sumg and future installed/browser acceptance mb-gnr9 remain open. Specs, QA procedure, roadmap, active release labels, PR descriptions and dependency graph are reconciled. mb-xada historical handoff is closed; #219/mb-dbue remain open awaiting a released tbd replacement. All future work extends Stack 218 and the whole stack stays held for stabilization and explicit landing approval. No GitHub URL/PR end-to-end pass, merge or release is claimed.
