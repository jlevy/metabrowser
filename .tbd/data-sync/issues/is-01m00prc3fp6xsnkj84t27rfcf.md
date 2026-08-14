---
type: is
id: is-01m00prc3fp6xsnkj84t27rfcf
title: Support bounded expansion of file-rollup subsection tails
kind: feature
status: open
priority: 1
version: 2
labels:
  - file-rollup-format
  - browser-api
dependencies:
  - type: blocks
    target: is-01m00prch1akzeds6rnwc4rkwy
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T17:57:42.628Z
updated_at: 2026-08-14T17:57:43.072Z
---
Extend the File Rollup Format and Metabrowser rollup projection so a consumer can expand a high-cardinality subsection without making the initial directory payload unbounded.

Required behavior:
- Preserve a bounded initial projection of each direct-child collection, with deterministic ordering, exact aggregate metrics for omitted children, and an omitted distinct-value count.
- Add a versioned, implementation-neutral way to request or represent the omitted child records against the same completed rollup snapshot. The design must work for semantic group families, family extensions, No extension basenames, and Other types extensions.
- Keep file and byte conservation for every population: the visible prefix plus remainder aggregate equals the subsection parent, and expanded children equal the former remainder aggregate.
- Key expansion to stable subsection identities and the rollup revision so live inventory changes cannot combine children from different snapshots.
- Bound every request and server operation. If a remainder needs paging internally, preserve deterministic continuation and let the UI reveal it atomically after acquisition rather than showing a misleading partial list.
- Keep the format general and consumer-agnostic; document the mechanism in file-rollup-format.md without hard-coding Metabrowser routes or UI labels.
- Replace the current fixed twenty-item compatibility assumption with documented initial and expansion bounds while retaining safe defaults.
- Update Python wire models, serializers, validation, API contracts, JavaScript normalization, conformance fixtures, conservation tests, and high-cardinality cases.
