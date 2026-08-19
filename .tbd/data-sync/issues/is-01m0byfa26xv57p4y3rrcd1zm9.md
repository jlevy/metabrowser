---
type: is
id: is-01m0byfa26xv57p4y3rrcd1zm9
title: "File Diff Format: standalone model doc, schemas, and conformance corpus"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m09s6rn8gpznqbygaqyqf3kq
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T02:44:12.997Z
updated_at: 2026-08-19T02:44:21.040Z
---
The change model defined completely, up front, as its own architecture doc under docs/project/architecture/file-diff-format/ — the File Rollup Format treatment. Complete taxonomy following git semantics as the reference: added/deleted/modified, rename-with-edit and folder moves, copies, mode changes, type changes (file/symlink/submodule), unmerged, binary transitions, missing trailing newlines, non-UTF-8 paths; hunk/line/intraline structure within files. JSON schemas plus a generated conformance corpus in data/ run against both the Python and browser models so the two sides cannot drift. Evaluate existing diff-model/unified-patch libraries against the format before writing any parser; the format, not a library, is the contract.
