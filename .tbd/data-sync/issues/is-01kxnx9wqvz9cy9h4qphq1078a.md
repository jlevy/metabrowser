---
type: is
id: is-01kxnx9wqvz9cy9h4qphq1078a
title: Add a generic writer event-log backend
kind: feature
status: open
priority: 2
version: 3
spec_path: TODO.md
labels:
  - indexing
  - plugins
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:05.787Z
updated_at: 2026-08-16T08:06:01.667Z
extensions:
  linear:
    id: 9bb812dc-1b93-47da-aa5b-1b140f267b4c
    linked_at: 2026-08-16T08:06:01.667Z
---
Define an optional generic append-only writer event-log backend with reconciliation, capability reporting, corruption handling, and deterministic tests. Core must not assume any consumer-specific state directory or event schema; applications may provide their own writers through the public contract.
