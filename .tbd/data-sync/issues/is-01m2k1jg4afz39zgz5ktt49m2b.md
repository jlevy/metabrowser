---
type: is
id: is-01m2k1jg4afz39zgz5ktt49m2b
title: "Hosted review Phase 0A.7: review and publish the formal stacked draft PR"
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/130
    at: 2026-09-15T19:09:57.836Z
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:27.913Z
updated_at: 2026-09-15T19:10:11.164Z
closed_at: 2026-09-15T19:10:11.164Z
close_reason: "Completed in draft PR #130: portable corpus, dormant browser parser, installed-distribution evidence, independent Fable review, full local verification, and final green GitHub CI. Post-stack landing is separately owned by mb-n2ro."
resolution: null
duplicate_of: null
---
Run the tbd precommit and code-review shortcuts, make verify, and tbd sync; review the exact diff for forbidden provider, network, cache, route, view, manifest, lockfile, and dependency changes. Push codex/v011-hosted-review-phase0a and open a draft GitHub PR based on codex/v011-hosted-review-design. Record the stack dependency on PR 125, exact validation, and follow-up Phase 0B blockers; watch all GitHub checks to a final green summary.

## Notes

Published draft PR https://github.com/jlevy/metabrowser/pull/130 from codex/v011-hosted-review-phase0a at 0e8819c6, based on codex/v011-hosted-review-design. Posted the Fable review record at https://github.com/jlevy/metabrowser/pull/130#issuecomment-5686510613. Final local make verify passed 2,148 tests (1 skipped), 124 goldens, lint/type/parity/hygiene, locked audits, wheel/sdist inspection, nine-plugin dormancy, and isolated-wheel smoke. GitHub CI is final green across distribution, lint, stack-integration, and Python 3.12/3.13/3.14/3.14t. Delivery review added mb-n2ro as the owned retarget/revalidation/merge gate before mb-pnz5.
