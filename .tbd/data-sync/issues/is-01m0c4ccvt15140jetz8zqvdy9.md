---
type: is
id: is-01m0c4ccvt15140jetz8zqvdy9
title: "diff/adapters/patch_file.py: unified-patch parser, no repository required"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4dez6h952zmcdd6rhsp2b
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:29.017Z
updated_at: 2026-08-19T04:28:17.869Z
---
parse_unified_patch(data) -> (ChangeSetManifest, dict[file_id, FilePatch]) with _split_file_sections, _parse_extended_headers (rename, copy, mode, similarity, binary, dissimilarity), _parse_hunk_header, _parse_hunk_body. Bounded by byte cap and section count. Malformed input yields an unsupported availability rather than an exception. This is the source that proves the format is standalone.
