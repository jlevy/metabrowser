---
type: is
id: is-01m2ned588n762bx755ernns3s
title: Upgrade tbd 0.9.0 surfaces and restore stacked-PR discoverability
kind: task
status: in_progress
priority: 1
version: 2
labels:
  - tooling
dependencies: []
created_at: 2026-09-16T15:47:13.286Z
updated_at: 2026-09-16T15:47:22.199Z
---
Upgrade the first-party get-tbd CLI to 0.9.0, run tbd setup --auto, commit the generated Metabrowser surfaces exactly as emitted, and verify that ordinary PR requests discover the stacked-prs shortcut and official gh-stack skill. The installed 0.9.0 package contains dist/docs/shortcuts/standard/stacked-prs.md and updated PR shortcuts, but tbd shortcut --list and tbd shortcut stacked-prs omit it. Audit the tbd source and open an upstream tbd PR with regression coverage and any required catalog/generator fix. Keep this tooling work separate from the hosted-review feature stack.

## Notes

Confirmed with get-tbd 0.9.0: the package includes dist/docs/shortcuts/standard/stacked-prs.md and updated PR/review/setup instructions, and gh stack v0.1.0 is installed, but tbd shortcut stacked-prs reports no match and shortcut --list omits it. Repository managed surfaces are stale. Work will refresh generated surfaces on a separate Metabrowser tooling branch and fix the upstream tbd registry/generator with tests.
