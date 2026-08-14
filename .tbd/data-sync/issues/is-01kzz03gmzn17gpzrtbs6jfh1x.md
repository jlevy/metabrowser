---
type: is
id: is-01kzz03gmzn17gpzrtbs6jfh1x
title: "Phase 3B: Complete Obsidian locations, media, and fixtures"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz211w19g9y39ct7qf0hy1z
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
created_at: 2026-08-14T02:02:36.062Z
updated_at: 2026-08-14T02:39:05.429Z
---
Complete required Obsidian behavior: map same-note and cross-note headings to actual rendered IDs; parse explicit ^block-id metadata from source and inject stable real DOM targets; route image and media wiki-embeds through bounded safe resources; preserve occurrence labels; and expose accessible pending, missing, ambiguous, and unsupported states without arbitrary selection. Add an Obsidian-style vault fixture with duplicate basenames, relative and vault-root paths, spaces, Unicode, headings, named blocks, attachments, embeds, incomplete indexing, and hostile targets. Document supported behavior and pass make verify. Whole-note or section transclusion, frontmatter alias lookup, backlinks, and graph views remain in mb-fbm2.
