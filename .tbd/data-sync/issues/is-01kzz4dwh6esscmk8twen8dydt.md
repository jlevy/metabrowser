---
type: is
id: is-01kzz4dwh6esscmk8twen8dydt
title: "Obsidian C: Map headings and named blocks to stable DOM targets"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dx62z79hwmqmec5z0kbb
parent_id: is-01kzz03gmzn17gpzrtbs6jfh1x
created_at: 2026-08-14T03:18:10.213Z
updated_at: 2026-08-14T04:53:26.515Z
closed_at: 2026-08-14T04:53:26.514Z
close_reason: Stable heading/block targets and safe attachment/media behavior pass focused and end-to-end tests.
---
Resolve same-note and cross-note wiki heading targets, including hierarchical forms, against actual rendered IDs. Parse explicit ^block-id metadata from source, remove or hide authoring markers as appropriate, inject stable real DOM targets, and navigate with canonical fragments. Never guess blocks from paragraph text. Add duplicate-heading, named-block, async-render, direct-load, and stale-scroll tests.
