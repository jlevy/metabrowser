---
type: is
id: is-01m0tb6n7zq5dvjf183rgwx1r1
title: Make zero-projection reads the provider checkpoint
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-08-24T16:56:03.070Z
updated_at: 2026-08-24T16:59:33.840Z
closed_at: 2026-08-24T16:59:33.839Z
close_reason: The provider contract now exposes a clear constant-work checkpoint without adding a handle method or dummy projection; shared contract coverage and the full repository gate pass.
resolution: null
duplicate_of: null
---
The catalog cache needs only the coherent read envelope (version, cursor, state, work), but currently sends a DiagnosticsQuery as a dummy projection. Make ReadRequest() with no projections the explicit constant-work checkpoint form, use it for validator/body-cache preflight, cover it in the shared provider contract harness, and document it so the fdu provider has no diagnostics coupling.

## Notes

ReadRequest() is now the explicit zero-projection checkpoint. Python returns a coherent version/cursor/state/work envelope with no inventory traversal; catalog validator/body-cache preflight uses it instead of DiagnosticsQuery. The shared provider harness requires zero projections and zero entry/directory/row work. Architecture, implementation plan, and changelog are updated. Focused 28-test coverage and full make verify pass with 1,556 tests plus one platform skip and 48 CLI goldens.
