---
type: is
id: is-01m0t9zsx9vhh3bzp96mqkaa4z
title: Measure navigation and catalog provider paths in serving benchmark
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - performance
  - inventory-provider
dependencies: []
parent_id: is-01m0t8bt30ykqhy4ksn5bs4ba4
child_order_hints:
  - is-01m0ta9e0vjj5c5bv4sagrdqks
created_at: 2026-08-24T16:34:49.896Z
updated_at: 2026-08-24T16:50:30.123Z
closed_at: 2026-08-24T16:50:30.122Z
close_reason: Serving benchmarks now measure and semantically validate navigation first/memo paths and catalog first/retained/304 paths for every provider; paired 100,000-file JSON evidence is clean and make verify passes.
resolution: null
duplicate_of: null
---
devtools/bench_serving.py records provider identity and work but its settled phase never calls /api/tree?depth=0 or /api/catalog, so navigation memo regressions, catalog scans on cache hits, and full catalog materialization are invisible. Add first-compute and repeated navigation timings plus catalog first-body, retained-body, and 304 timings; verify stable validators and semantic bodies; include them in JSON/report comparisons and tests so the same axes apply to Python and fdu.

## Notes

Extended phase_settled and report rows with first and repeated root navigation plus first-body, retained-body, and conditional-304 catalog paths. The harness validates navigation totals against the settled walker, exact repeated catalog body/ETag identity, complete nonempty catalog shape, and empty 304 bodies. The paired 100,000-file run has identical 5,065,580-byte catalogs and no semantic errors: navigation memo p50 44.1 to 0.8 ms, retained catalog body 574.1 to 2.5 ms, catalog 304 577.9 to 1.0 ms, and settled provider visits 5,939,859 to 1,291,395. Full make verify remains.
