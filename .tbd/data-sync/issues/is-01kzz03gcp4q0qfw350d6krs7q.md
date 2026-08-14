---
type: is
id: is-01kzz03gcp4q0qfw350d6krs7q
title: "Phase 3A: Parse Obsidian wiki-links and resolve notes"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz03gmzn17gpzrtbs6jfh1x
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
created_at: 2026-08-14T02:02:35.798Z
updated_at: 2026-08-14T02:39:05.171Z
---
Add a bounded source-aware wiki parser before final HTML decoration; preserve escape, code-span, fenced-block, and existing-link context and do not regex arbitrary rendered HTML. Convert [[Note]], explicit paths, occurrence labels, same-note and cross-note headings, named-block subpaths, and media embed syntax into the shared LinkIntent. Use exact relative and vault-path precedence, optional .md for notes, then a bounded completion-aware suffix or basename index only for unique matches. Return explicit pending, ambiguous, missing, unsafe, and unsupported results, retain candidates, and never alter exact standard Markdown semantics. Include parser, index, bounds, ambiguity, subscription, and disposal tests; run make verify.
