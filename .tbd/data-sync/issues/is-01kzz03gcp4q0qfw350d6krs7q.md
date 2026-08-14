---
type: is
id: is-01kzz03gcp4q0qfw350d6krs7q
title: "Phase 3A: Parse Obsidian wiki-links and resolve notes"
kind: feature
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz03gmzn17gpzrtbs6jfh1x
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
child_order_hints:
  - is-01kzz4dvt6208xkx40mj4rbxps
  - is-01kzz4dw3cv7ct4fm76xxw9n9r
created_at: 2026-08-14T02:02:35.798Z
updated_at: 2026-08-14T04:56:22.485Z
closed_at: 2026-08-14T04:53:26.287Z
close_reason: Obsidian syntax and note-resolution feature is complete and verified.
---
Add a bounded source-aware wiki parser before final HTML decoration; preserve escape, code-span, fenced-block, and existing-link context and do not regex arbitrary rendered HTML. Convert [[Note]], explicit paths, occurrence labels, same-note and cross-note headings, named-block subpaths, and media embed syntax into the shared LinkIntent. Use exact relative and vault-path precedence, optional .md for notes, then a bounded completion-aware suffix or basename index only for unique matches. Return explicit pending, ambiguous, missing, unsafe, and unsupported results, retain candidates, and never alter exact standard Markdown semantics. Include parser, index, bounds, ambiguity, subscription, and disposal tests; run make verify.
