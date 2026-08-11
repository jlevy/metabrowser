---
type: is
id: is-01kyxyzjxyh94a9re1jps0mv23
title: "Spike 3: implement and profile the fuzzy matcher"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxyztmrk2yqjb8hz1trvt4e
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:08:02.493Z
updated_at: 2026-08-01T06:50:01.605Z
closed_at: 2026-08-01T06:50:01.604Z
close_reason: Implemented the deterministic fixture-driven fuzzy matcher with named rank components, original-path ranges, stable ties, Unicode case handling, and public 2,000/50,000-candidate profiles; make verify passes.
---
Use TDD to implement the dependency-free strict file_fuzzy_match module against the ranking fixture. Return named rank components and original-string match ranges; compare exact basename, basename prefix, contiguous and boundary matches, subsequences, path segments, gaps, length, depth, and stable path ties in the documented order. Add fixture diagnostics that show why an order changed. Measure scorer throughput on public synthetic catalogs at Recent-sized and heavily expanded scales, recording evidence rather than inventing an index or Worker.
