---
type: is
id: is-01kzz4dvt6208xkx40mj4rbxps
title: "Obsidian A: Parse source-aware wiki-link syntax"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dw3cv7ct4fm76xxw9n9r
parent_id: is-01kzz03gcp4q0qfw350d6krs7q
created_at: 2026-08-14T03:18:09.477Z
updated_at: 2026-08-14T04:56:22.707Z
closed_at: 2026-08-14T04:53:26.039Z
close_reason: Source-aware wiki parsing and deterministic completion-aware vault lookup pass parser, resolver, lifecycle, and bounds tests.
---
Add a bounded Markdown-aware scanner or KPress integration that recognizes note links, explicit paths, occurrence labels, same-note and cross-note headings, hierarchical headings, named blocks, attachment links, and image/media embeds before source context is lost. Preserve code spans, fenced blocks, existing Markdown links, and escaped literals. Emit inert sanitizable metadata and shared LinkIntent values; do not regex arbitrary rendered HTML. Add parser and budget tests.
