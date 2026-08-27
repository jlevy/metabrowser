---
type: is
id: is-01m1071kxf5nkk1dn2hdfkjq2m
title: Prepare and publish Metabrowser v0.8.0
kind: task
status: closed
priority: 1
version: 4
labels:
  - release:v0.8.0
dependencies: []
created_at: 2026-08-26T23:38:50.158Z
updated_at: 2026-08-27T00:43:36.594Z
closed_at: 2026-08-27T00:43:36.593Z
close_reason: Metabrowser v0.8.0 was prepared, compared against v0.7.1, validated, merged, tagged, published through trusted publishing, verified on public PyPI and GitHub, smoke-tested through the public Agent Skill, installed globally, and opened on the representative repository.
resolution: null
duplicate_of: null
---
Cut a release-preparation branch from current main, reconcile the merged user-visible delta and open release tracking, compare the exact candidate with v0.7.1, run the full release gate, land the release PR, create v0.8.0, watch trusted publishing, and verify the public artifact and Agent Skill installation.

## Notes

Release scope explicitly retains the bounded 500-commit Git panel from v0.7.1. The unbounded-history epic and its five implementation beads move together to v0.9.0; v0.8.0 ships the already merged diff, syntax, retained navigation, commit-summary, plugin-contract, and performance-gate improvements.
