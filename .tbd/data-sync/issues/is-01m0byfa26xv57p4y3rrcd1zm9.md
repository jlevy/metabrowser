---
type: is
id: is-01m0byfa26xv57p4y3rrcd1zm9
title: "File Diff Format: standalone model doc, schemas, and conformance corpus"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m09s6rn8gpznqbygaqyqf3kq
  - type: blocks
    target: is-01m0c4cbscxq3b0qe4zcw6250j
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T02:44:12.997Z
updated_at: 2026-08-19T04:40:28.089Z
---
The change model defined completely, up front, as its own architecture doc under docs/project/architecture/file-diff-format/ — the File Rollup Format treatment. Complete taxonomy following git semantics as the reference: added/deleted/modified, rename-with-edit and folder moves, copies, mode changes, type changes (file/symlink/submodule), unmerged, binary transitions, missing trailing newlines, non-UTF-8 paths; hunk/line/intraline structure within files. AUTHORITY: the neutral JSON Schema is the contract (third instance of the repo pattern). Python implements it with Pydantic models — already a runtime dep and the established idiom for validated documents (plugin_loader/manifest.py); discriminated unions on change kind. Browser implements it as types.d.ts plus the corpus validator; no Zod — the corpus provides that guarantee and the npm posture is decided once, at the Phase 3 renderer gate. ORACLE: a fully hydrated change set applied to the base tree (through a content resolver) must reproduce the target tree by tree-hash equality — modes, symlinks, renames, type changes included. Availability states are declared gaps in applicability. Evaluate existing diff-model/unified-patch libraries against the format before writing any parser; the format, not a library, is the contract.
