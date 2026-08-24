---
type: is
id: is-01m0t6s5k2my3fnaxnm31sfbm5
title: Reject performance-loop records without provider contract identity
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
created_at: 2026-08-24T15:38:46.753Z
updated_at: 2026-08-24T15:40:14.979Z
closed_at: 2026-08-24T15:40:14.978Z
close_reason: Performance-loop records now require one complete, consistent provider/contract identity, reject missing or conflicting sources, and canonicalize the recorded identity; focused gate tests pass.
resolution: null
duplicate_of: null
---
Make explorations/performance-loop/run.py::cmd_record enforce the documented measurement invariant: the live server must report both the requested provider and inventory-provider-v1 contract through diagnostics or its walk record. Reject missing, mismatched, or conflicting identities and add coverage in tests/test_performance_loop_gate.py.
