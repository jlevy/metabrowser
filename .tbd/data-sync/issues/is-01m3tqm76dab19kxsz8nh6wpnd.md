---
type: is
id: is-01m3tqm76dab19kxsz8nh6wpnd
title: Help text for --untrusted and --no-active-content describes only the /raw sandbox, not inert Markdown and the CSP
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T03:20:15.820Z
updated_at: 2026-10-01T03:20:15.820Z
---
Found during the docs reconciliation (PR #250): src/metabrowser/cli/main.py:521-537 help text for --untrusted and --no-active-content still describes only the /raw sandbox, though on the v0.12 stack both flags also render Markdown inert and apply the strict Content-Security-Policy to a folder on disk (CHANGELOG 'Changed for a folder on disk'). Update the two help strings and the cli-surface golden; keep docs/command-line.md consistent.
