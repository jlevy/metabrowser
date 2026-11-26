---
type: is
id: is-01m8cn7pfer7dn5f1em8t8xhv8
title: Maintain the SoftSchema table index after one file changes
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8cn7rkh3hmx5phmv0f35nf1
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
created_at: 2026-11-26T19:27:35.402Z
updated_at: 2026-11-26T19:27:37.584Z
---
Use file events as dirty hints and reconcile safely. Replace only affected rows, IDs and relationship edges; publish a new generation atomically; retain the last complete generation after interruption. Cache hot metadata and pages in memory while persistence stays bounded. Verify app and CLI see the update.
