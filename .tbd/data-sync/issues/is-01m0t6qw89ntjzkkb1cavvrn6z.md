---
type: is
id: is-01m0t6qw89ntjzkkb1cavvrn6z
title: Keep provider identity validation compatible with skipped cold scans
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:38:04.422Z
updated_at: 2026-08-24T15:40:01.634Z
closed_at: 2026-08-24T15:40:01.633Z
close_reason: Identity validation now ignores phases absent by explicit benchmark configuration but still rejects present phases without identity; focused benchmark tests pass.
resolution: null
duplicate_of: null
---
Fix devtools/bench_serving.py::_record_inventory_identity so --skip-cold-scan validates only phases that actually ran while still requiring identity on every present phase. Add focused tests in tests/test_bench_serving.py for skipped-phase success and missing identity failure.
