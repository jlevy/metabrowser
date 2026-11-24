---
type: is
id: is-01m87spmzn3z3qx3vgcgkeqqjw
title: Pin the environment Metabrowser runs gh with
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
created_at: 2026-11-24T22:09:27.535Z
updated_at: 2026-11-24T22:09:27.535Z
---
Threat model T9. builtin_plugins/github/gh.py gh_environment drops _DROPPED_ENV and sets prompt and color variables; no test references it. Add a test that pins what is dropped and set, and that GH_TOKEN/GITHUB_TOKEN pass through unlogged.
