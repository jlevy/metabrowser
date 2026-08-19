---
type: is
id: is-01m0c4cch7txk2nfb9fwqk6nxq
title: "diff/adapters/base.py: the DiffSource port"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4ccvt15140jetz8zqvdy9
  - type: blocks
    target: is-01m0c4cxzv2gzbbxp15796r65j
  - type: blocks
    target: is-01m0c4dez6h952zmcdd6rhsp2b
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:28.678Z
updated_at: 2026-08-19T04:28:17.886Z
---
class DiffSource(Protocol) with resolve(intent) -> ResolvedComparison, manifest(resolved) -> ChangeSetManifest, file_patch(resolved, file_id) -> FilePatch, content(resolved, file_id, side) -> AsyncIterator[bytes]. Four methods, no source-specific vocabulary. Deliberately small: it is the seam that keeps patch-file, git, hosted, and document-edit sources interchangeable.
