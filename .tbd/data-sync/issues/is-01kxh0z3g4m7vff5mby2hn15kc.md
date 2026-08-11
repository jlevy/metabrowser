---
type: is
id: is-01kxh0z3g4m7vff5mby2hn15kc
title: Load dotenv for remote commands
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T19:16:54.404Z
updated_at: 2026-07-17T21:16:43.902Z
closed_at: 2026-07-14T19:18:45.682Z
close_reason: Loaded the shared dotenv chain before remote configuration, added GCP project regression coverage, and passed all 615 tests and package gates
---
Load the shared dotenv chain before remote command configuration so METABROWSER_GCP_PROJECT and related settings behave consistently with serve, walk, and plugins; add regression coverage.
