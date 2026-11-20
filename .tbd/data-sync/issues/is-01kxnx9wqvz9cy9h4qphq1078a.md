---
type: is
id: is-01kxnx9wqvz9cy9h4qphq1078a
title: Add a generic writer event-log backend
kind: feature
status: open
priority: 2
version: 4
spec_path: TODO.md
labels:
  - indexing
  - plugins
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:05.787Z
updated_at: 2026-11-20T19:15:57.011Z
extensions: {}
---
Define an optional generic append-only writer event-log backend with reconciliation, capability reporting, corruption handling, and deterministic tests. Core must not assume any consumer-specific state directory or event schema; applications may provide their own writers through the public contract.
