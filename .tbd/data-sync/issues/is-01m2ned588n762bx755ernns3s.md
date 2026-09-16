---
type: is
id: is-01m2ned588n762bx755ernns3s
title: Upgrade tbd 0.9.0 surfaces and restore stacked-PR discoverability
kind: task
status: in_progress
priority: 1
version: 5
labels:
  - tooling
dependencies: []
created_at: 2026-09-16T15:47:13.286Z
updated_at: 2026-09-16T18:25:02.324Z
---
Upgrade the first-party get-tbd CLI to 0.9.0, run tbd setup --auto, commit the generated Metabrowser surfaces exactly as emitted, and verify that ordinary PR requests discover the stacked-prs shortcut and official gh-stack skill. The installed 0.9.0 package contains dist/docs/shortcuts/standard/stacked-prs.md and updated PR shortcuts, but tbd shortcut --list and tbd shortcut stacked-prs omit it. Audit the tbd source and open an upstream tbd PR with regression coverage and any required catalog/generator fix. Keep this tooling work separate from the hosted-review feature stack.

## Notes

Upgraded the global first-party CLI to get-tbd 0.9.0 and regenerated MetaBrowser managed tbd surfaces with `tbd setup --auto`. Confirmed `tbd shortcut stacked-prs` is present and readable.

Opened upstream tbd PR #301 (https://github.com/jlevy/tbd/pull/301) to make stacked/dependent PR intent route explicitly from the generated top-level AGENTS.md block and every skill tier; distinguish chained branches from formal `gh stack` membership; handle remote-only formal stacks; preserve draft state; harden sync, checkout, and diff-base postconditions; emit owning-agent installers; validate the pinned official skill identity; and authenticate the pinned extension artifact before publication.

The documented review path includes:
- the initial independent review and fixes for remote-only classification, diff-base selection, and exact skill identity;
- a senior review tracked by parent `tbd-9yi5` and children `tbd-k00n`, `tbd-g3la`, `tbd-e6uf`, and `tbd-6tz7`, all fixed in `5fbd858b`;
- downstream executable-integrity finding `tbd-wmoh`, fixed in `048ce4dc` with isolated verified staging and publication-race detection;
- two follow-up installer publication reviews, with the final independent review reporting no findings.

Upstream validation passes locally: 176 test files; 2,679 tests passed and 1 skipped; 100 focused installer/setup/integration tests; formatting, lint, typecheck, build, action pins, generated-surface comparisons, transcript, and package validation. Final GitHub CI for `048ce4dc` is being watched to completion.

Opened MetaBrowser draft PR #137 (https://github.com/jlevy/metabrowser/pull/137) with exact released-0.9.0 generated output. MetaBrowser `make verify` and the pre-push gate passed: 2,124 tests passed, 1 skipped; 124 golden cases; lint, type, parity, public-hygiene, supply-chain, audit, build, installed-artifact, and distribution checks. Its GitHub CI is fully green.

PR #137 remains draft until #301 lands and a tbd patch release is cut. Then rerun the released `tbd setup --auto`, review the corrected generated delta, rerun `make verify`, push, and watch CI. Do not hand-patch generated MetaBrowser surfaces.
