---
type: is
id: is-01m0dmjfnekkf22fb5zhmj1nke
title: "Diff view: syntax highlighting over old/new streams"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T18:29:40.141Z
updated_at: 2026-08-24T21:58:03.634Z
---
Add bounded progressive syntax highlighting to the diff renderer. Reconstruct and highlight each hunk's old and new source independently, split token spans back onto stable line records, and reuse the regular source grammar registry and semantic palette over transparent token backgrounds. Unified deletion rows consume old tokens, addition rows consume new tokens, and context consumes the new side. Keep plain text as the fallback for unknown languages, unavailable assets, and over-limit input. The focused plan also defines the shared line model used by the split projection.

## Notes

2026-08-24 planning review complete. The focused spec selects per-hunk old/new token streams, the existing Highlight.js palette and bound, plain-first enhancement, and one semantic model for unified and split projections. Current GitHub, React Diff View, CodeMirror, Monaco, and git diff-highlight behavior informed the decisions. Implementation remains open.
