---
type: is
id: is-01m0c4cbscxq3b0qe4zcw6250j
title: "diff/format.py: Pydantic models implementing the checked-in schema"
kind: feature
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4cc698vj8c0qmfvtw24ad
  - type: blocks
    target: is-01m0c4cch7txk2nfb9fwqk6nxq
  - type: blocks
    target: is-01m0c4ccvt15140jetz8zqvdy9
  - type: blocks
    target: is-01m0c4cyrd1jqse6z0rxt0kh2k
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:27.897Z
updated_at: 2026-08-19T04:51:08.633Z
closed_at: 2026-08-19T04:51:08.632Z
close_reason: Landed on claude/diff-core with corpus + oracle + parser tests (50 passing).
---
Enums ChangeKind, EntryType, FileMode, Availability, Side. Models ContentRef, IntralineSpan, LineRecord, Hunk, FilePatch, FileChange, ChangeSetManifest, ResolvedComparison, ComparisonIntent. FileChange is a discriminated union on kind so a rename carries old_path and similarity by construction and a type change carries both entry types. load_schema() reads the checked-in JSON Schema; validate_document(doc) is what the conformance corpus drives from the Python side. BaseModel + ConfigDict(extra='forbid'), matching plugin_loader/manifest.py.
