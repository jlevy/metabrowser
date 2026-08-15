---
type: is
id: is-01kzz03gmzn17gpzrtbs6jfh1x
title: "Phase 3B: Complete Obsidian locations, media, and fixtures"
kind: feature
status: closed
priority: 1
version: 17
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz211w19g9y39ct7qf0hy1z
  - type: blocks
    target: is-01kzz4ehz2b8pr1xky5hvgr2mp
  - type: blocks
    target: is-01kzz4ejb1vfze0y8w15cjaf5g
  - type: blocks
    target: is-01kzz4ejm8kxev59qawa3a9yqd
  - type: blocks
    target: is-01kzz4ejxjnsbteg74etbkzsst
  - type: blocks
    target: is-01kzz4ek6wxf50va32ymc7x80h
  - type: blocks
    target: is-01kzz4ekfzfqz35v7rwrx3esfk
  - type: blocks
    target: is-01kzz4eksmrezrggyrjefynntk
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
child_order_hints:
  - is-01kzz4dwh6esscmk8twen8dydt
  - is-01kzz4dwwjgch14nr5rhh2j1vm
  - is-01kzz4dx62z79hwmqmec5z0kbb
created_at: 2026-08-14T02:02:36.062Z
updated_at: 2026-08-14T04:56:23.411Z
closed_at: 2026-08-14T04:53:26.966Z
close_reason: Obsidian locations, media, and fixture feature is complete and verified.
---
Complete required Obsidian behavior: map same-note and cross-note headings to actual rendered IDs; parse explicit ^block-id metadata from source and inject stable real DOM targets; route image and media wiki-embeds through bounded safe resources; preserve occurrence labels; and expose accessible pending, missing, ambiguous, and unsupported states without arbitrary selection. Add an Obsidian-style vault fixture with duplicate basenames, relative and vault-root paths, spaces, Unicode, headings, named blocks, attachments, embeds, incomplete indexing, and hostile targets. Document supported behavior and pass make verify. Whole-note or section transclusion, frontmatter alias lookup, backlinks, and graph views remain in mb-fbm2.
