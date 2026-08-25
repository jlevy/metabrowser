---
type: is
id: is-01m0w0k1ssnxxzvz9qrnqdg2rt
title: "PR #74 scope audit S5: replace generic diagnostics map and delete unused metadata query"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:29:03.671Z
updated_at: 2026-08-25T08:29:03.671Z
---
The sealed query algebra currently has an arbitrary DiagnosticsProjection.counters mapping, despite the no-generic-escape-hatch rule, while MetadataQuery/MetadataProjection have no production consumer and duplicate provider identity. Replace diagnostics with one frozen, constant-size typed payload containing the actually consumed identity, index counts, watcher summary, read count, and cumulative WorkCounters; delete the unused metadata kind and duplicate/unconsumed diagnostic fields; update routes, conformance registry, architecture, and FDU handoff.
