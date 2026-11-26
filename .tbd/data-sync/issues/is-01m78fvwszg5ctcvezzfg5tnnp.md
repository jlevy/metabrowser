---
type: is
id: is-01m78fvwszg5ctcvezzfg5tnnp
title: Declare a compatible range for Softschema
kind: task
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:06.238Z
updated_at: 2026-11-26T08:37:20.268Z
started_at: 2026-11-26T08:35:34.356Z
---
Phase 0, a standalone pull request to main (plan: Implementation Plan, Phase 0). Replace softschema==0.8.1 with softschema>=0.8.1,<0.10, keep the exact version in uv.lock, record the newer end as an audited first-party selection in SUPPLY-CHAIN-SECURITY.md with its uv.toml exclude-newer-package entry, and add a CI job that installs beside a package needing it. KPress stays exact: docs/development.md says its rendering contract is part of the release surface. Reproduced: metabrowser==0.12.0 with softschema>=0.9.1,<0.10 has no solution, and pyproject.toml on main still pins 0.8.1. The workflow library carries a Softschema override until a release does this.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
