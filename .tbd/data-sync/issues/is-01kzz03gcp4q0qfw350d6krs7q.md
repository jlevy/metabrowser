---
type: is
id: is-01kzz03gcp4q0qfw350d6krs7q
title: "Phase 2A: Parse Obsidian wiki-links and resolve unique notes"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz03gmzn17gpzrtbs6jfh1x
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
created_at: 2026-08-14T02:02:35.798Z
updated_at: 2026-08-14T02:02:36.062Z
---
Add a Markdown-plugin wiki parser for eligible rendered text outside code and existing links. Convert [[Note]], explicit paths, labels, headings, block subpaths, and media embed syntax into the shared LinkIntent. Reuse exact path precedence, then a bounded inventory-derived suffix or basename index only for unique note matches; return explicit ambiguous, missing, incomplete, and unsupported results. Keep standard Markdown exact. Include parser, index, ambiguity, bounds, and disposal tests; run make verify.
