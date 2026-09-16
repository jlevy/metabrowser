---
type: is
id: is-01m2ned588n762bx755ernns3s
title: Upgrade tbd 0.9.0 surfaces and restore stacked-PR discoverability
kind: task
status: in_progress
priority: 1
version: 6
labels:
  - tooling
dependencies: []
created_at: 2026-09-16T15:47:13.286Z
updated_at: 2026-09-16T19:01:11.482Z
---
Upgrade the first-party get-tbd CLI to 0.9.0, run tbd setup --auto, commit the generated Metabrowser surfaces exactly as emitted, and verify that ordinary PR requests discover the stacked-prs shortcut and official gh-stack skill. The installed 0.9.0 package contains dist/docs/shortcuts/standard/stacked-prs.md and updated PR shortcuts, but tbd shortcut --list and tbd shortcut stacked-prs omit it. Audit the tbd source and open an upstream tbd PR with regression coverage and any required catalog/generator fix. Keep this tooling work separate from the hosted-review feature stack.

## Notes

Upgraded the global first-party CLI to get-tbd 0.9.0 and regenerated MetaBrowser managed surfaces with `tbd setup --auto`. Opened draft MetaBrowser PR #137 (https://github.com/jlevy/metabrowser/pull/137) with exact released-0.9.0 generated output; no hand patches.

Upstream tbd PR #301 (https://github.com/jlevy/tbd/pull/301) merged the core fixes: explicit ordinary-vs-stacked routing in the main managed block, formal remote stack postconditions, safe checkout/sync/diff-base behavior, owning-agent installers, exact pinned skill identity, and digest-verified isolated extension publication. Its documented review path includes initial independent review, senior review parent `tbd-9yi5` and children `tbd-k00n`, `tbd-g3la`, `tbd-e6uf`, `tbd-6tz7`, plus executable-integrity bead `tbd-wmoh`.

A final independent audit found that portable/brief/minimal skill tiers still lacked the explicit invariant that chained branch bases are not formal GitHub stack membership. That audit is tracked by parent `tbd-gpsc` and findings `tbd-l5me` and `tbd-4rk5`, now closed. Windows CI also showed the new installer harness assumed POSIX paths; `tbd-7xt4` tracks the test-only portability fix.

Because #301 merged concurrently at an intermediate commit, focused follow-up tbd PR #304 (https://github.com/jlevy/tbd/pull/304) carries the remaining every-surface discoverability fix and keeps all 35 installer integrity tests active on Windows instead of skipping them. Final independent review of #304 reported no findings. Focused validation is 102/102; formatting, lint, typecheck, build, generated comparisons, and diff checks pass. A full pre-push run on the exact tree passed 176 files with 2,681 tests passed and 1 skipped; unrelated load-sensitive tests also passed in isolation. GitHub CI, including Windows, is being watched to completion.

MetaBrowser validation remains green: `make verify`, pre-push, and GitHub CI passed (2,124 tests, 1 skipped; 124 golden cases; lint/type/parity/public-hygiene/supply-chain/audits/build/distribution).

PR #137 remains draft until #304 lands and a tbd patch release is cut. Then rerun the released `tbd setup --auto`, review the generated delta, run `make verify`, push, and watch CI. Do not hand-patch generated MetaBrowser surfaces.
