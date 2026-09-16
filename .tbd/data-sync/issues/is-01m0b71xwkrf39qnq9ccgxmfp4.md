---
type: is
id: is-01m0b71xwkrf39qnq9ccgxmfp4
title: "Hosted review Phase 4: anchored review threads over comparisons"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2kw2dcatp87s48y8ra11jp4
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-08-18T19:54:57.298Z
updated_at: 2026-09-16T01:07:32.361Z
---
Implement provider-neutral ReviewThread and frontmatter ReviewComment views over a closed tagged ReviewAnchor union: file-only, one-line, and range forms with side/orientation, immutable comparison and revision IDs, path, and context fingerprint. GitHub is the first producer. Map only with sufficient Git identity and context; otherwise preserve the provider anchor as outdated, unresolved, or unmappable without inventing a line. Include file-level, outdated-range, deleted-file, and remapped fixtures; never extend File Diff Format.
