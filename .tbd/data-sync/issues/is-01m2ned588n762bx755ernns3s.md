---
type: is
id: is-01m2ned588n762bx755ernns3s
title: Upgrade tbd 0.9.0 surfaces and restore stacked-PR discoverability
kind: task
status: in_progress
priority: 1
version: 4
labels:
  - tooling
dependencies: []
created_at: 2026-09-16T15:47:13.286Z
updated_at: 2026-09-16T17:18:46.269Z
---
Upgrade the first-party get-tbd CLI to 0.9.0, run tbd setup --auto, commit the generated Metabrowser surfaces exactly as emitted, and verify that ordinary PR requests discover the stacked-prs shortcut and official gh-stack skill. The installed 0.9.0 package contains dist/docs/shortcuts/standard/stacked-prs.md and updated PR shortcuts, but tbd shortcut --list and tbd shortcut stacked-prs omit it. Audit the tbd source and open an upstream tbd PR with regression coverage and any required catalog/generator fix. Keep this tooling work separate from the hosted-review feature stack.

## Notes

Upgraded the global first-party CLI to get-tbd 0.9.0 and regenerated MetaBrowser's managed tbd surfaces with tbd setup --auto. Confirmed tbd shortcut stacked-prs is now present and readable. Opened upstream tbd PR #301 (https://github.com/jlevy/tbd/pull/301) to make stacked/dependent PR intent route explicitly from generated top-level AGENTS.md and every skill tier, distinguish chained branches from formal gh stack membership, handle remote-only formal stacks, harden diff-base selection, emit owning-agent installers, and validate the exact pinned official skill identity. Independent subagent review found three issues; all were fixed and documented on the PR. Upstream CI is fully green. Opened MetaBrowser draft PR #137 (https://github.com/jlevy/metabrowser/pull/137) with the exact 0.9.0 generated output. MetaBrowser make verify and the pre-push gate passed: 2124 tests passed, 1 skipped; 124 golden cases passed; lint/type/parity/supply-chain/audits/distribution checks passed. PR #137 remains draft until #301 lands, a tbd patch release is cut, and tbd setup --auto regenerates the corrected Codex installer and top-level routing without hand-patching generated output.
