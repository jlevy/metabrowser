---
type: is
id: is-01m0txjq0p04ce7q120wr114ez
title: "PR #74 review MB74-C2: make CPU work timing exact-or-absent"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0txhaybmj82ym2wcm85zz0b
created_at: 2026-08-24T22:17:12.469Z
updated_at: 2026-08-24T22:36:10.778Z
closed_at: 2026-08-24T22:36:10.777Z
close_reason: "Fixed: WorkCounters.cpu_time_ns is exact-or-absent, aggregation propagates unavailability, the debug surface preserves null, and contract/coordinator tests cover present, absent, and invalid values."
resolution: null
duplicate_of: null
---
Source: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5401198953. docs/project/architecture/arch-inventory-provider.md:213 and docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md:145 currently require CPU time. Align the provider contract with exact-or-absent measurement using an optional cpu_ns field, never a fabricated zero or inferred value, and test exactness and availability semantics when present.
