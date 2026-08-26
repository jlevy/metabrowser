---
type: is
id: is-01m1071kxf5nkk1dn2hdfkjq2m
title: Prepare and publish Metabrowser v0.8.0
kind: task
status: in_progress
priority: 1
version: 2
labels:
  - release:v0.8.0
dependencies: []
created_at: 2026-08-26T23:38:50.158Z
updated_at: 2026-08-26T23:39:02.622Z
---
Cut a release-preparation branch from current main, reconcile the merged user-visible delta and open release tracking, compare the exact candidate with v0.7.1, run the full release gate, land the release PR, create v0.8.0, watch trusted publishing, and verify the public artifact and Agent Skill installation.
