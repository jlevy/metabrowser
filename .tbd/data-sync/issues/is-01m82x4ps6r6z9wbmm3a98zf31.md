---
type: is
id: is-01m82x4ps6r6z9wbmm3a98zf31
title: Align PR Overview header rhythm with the commit header
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/718
    at: 2026-11-23T00:46:43.029Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:33:21.656Z
updated_at: 2026-11-23T01:42:40.920Z
started_at: 2026-11-23T00:40:55.054Z
closed_at: 2026-11-23T01:42:40.920Z
close_reason: "Independently reviewed and merged in #718 at 44c475dd5 after exact PR and current main checks passed. Real Chrome verified state, author, and branches order, the shared 21-point size row and the measured vertical spacing while preserving Commit geometry."
resolution: null
duplicate_of: null
---
Use the existing commit page as the visual reference for the PR Overview. Compare real rendered header sequencing and vertical spacing, reuse the established shared page-header patterns where rows match, and preserve the explicitly requested PR state/age, author, and branch ordering.
