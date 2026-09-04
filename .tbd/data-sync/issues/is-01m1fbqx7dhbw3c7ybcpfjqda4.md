---
type: is
id: is-01m1fbqx7dhbw3c7ybcpfjqda4
title: Release Metabrowser 0.9.1 for lazy plugin view correctness
kind: task
status: closed
priority: 0
version: 3
labels: []
dependencies: []
created_at: 2026-09-01T20:49:31.372Z
updated_at: 2026-09-01T21:49:39.651Z
closed_at: 2026-09-01T21:49:39.649Z
close_reason: Released Metabrowser 0.9.1 from maintenance merge 16211ccb via PR 103; exact-head hosted CI, trusted PyPI publish workflow, metadata, wheel install, version, and plugin doctor all passed.
resolution: null
duplicate_of: null
---
Backport the merged lazy plugin renderer fix from PR 102 onto v0.9.0, prepare a patch release that contains no post-0.9.0 feature work, run the required release comparison and make verify, land the release PR, publish through the documented GitHub release workflow, verify PyPI, and update the Trading pin to the immutable published wheel.
