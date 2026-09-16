---
type: is
id: is-01m2ned588n762bx755ernns3s
title: Upgrade tbd 0.9.0 surfaces and restore stacked-PR discoverability
kind: task
status: in_progress
priority: 1
version: 7
labels:
  - tooling
dependencies: []
created_at: 2026-09-16T15:47:13.286Z
updated_at: 2026-09-16T19:54:14.315Z
---
Upgrade the first-party get-tbd CLI to 0.9.0, run tbd setup --auto, commit the generated Metabrowser surfaces exactly as emitted, and verify that ordinary PR requests discover the stacked-prs shortcut and official gh-stack skill. The installed 0.9.0 package contains dist/docs/shortcuts/standard/stacked-prs.md and updated PR shortcuts, but tbd shortcut --list and tbd shortcut stacked-prs omit it. Audit the tbd source and open an upstream tbd PR with regression coverage and any required catalog/generator fix. Keep this tooling work separate from the hosted-review feature stack.

## Notes

MetaBrowser draft PR #137 (https://github.com/jlevy/metabrowser/pull/137) contains the exact released tbd 0.9.0 generated surfaces; it is intentionally not hand-patched. Local make verify, pre-push, and GitHub CI are green (2,124 tests passed, 1 skipped; 124 golden cases). Upstream tbd PR #301 merged the core ordinary-vs-stacked routing, formal gh stack postconditions, owning-agent selection, exact skill identity, and verified extension publication. Follow-up tbd PR #304 (https://github.com/jlevy/tbd/pull/304) completes portable/brief/minimal discoverability and keeps all installer integrity tests active on Windows. Its final commit d4f6169c passed Actions run 35142252445 across Windows, macOS, both Ubuntu jobs, Coverage & Lint, Benchmark, and secret scanning; independent final review found no actionable issues. The hosted Windows follow-up is tracked and closed as tbd-vmyv, with findings and resolutions documented on PR #304. Keep #137 draft until #304 merges and a tbd patch release is cut; then rerun the released tbd setup --auto, review the generated delta, run make verify, push, and watch CI.
