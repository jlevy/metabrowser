---
type: is
id: is-01m0w062fn61tjrdp37vnga45p
title: Research and plan VS Code-derived intraline diff refinement
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: codex@spud10
labels:
  - diff
dependencies: []
parent_id: is-01kxse0wddy6je24t1dm5caber
hold: null
hold_until: null
created_at: 2026-08-25T08:21:58.388Z
updated_at: 2026-08-25T08:32:17.050Z
started_at: 2026-08-25T08:22:02.211Z
closed_at: 2026-08-25T08:32:17.050Z
close_reason: Research, plan, documentation reconciliation, and full validation complete.
resolution: null
duplicate_of: null
---
Audit existing diff research and architecture, inspect current GitHub rendering and primary-source algorithms, check out pinned VS Code diff source into ignored attic/, and extend the active roadmap with a file- and function-aware intraline refinement phase. Reconcile the completed syntax/layout addendum and normative File Diff Format ownership without changing the wire schema.

## Notes

Completed. Checked out microsoft/vscode sparsely under ignored attic/vscode at 77f86f3d3a05cf5d6f765705e816341c918b7dae via the third-party checkout shortcut. Reviewed GitHub PR #76 live, Git diff-highlight, CodeMirror merge, jsdiff, current Metabrowser model/render seams, both prior research docs, the completed syntax/layout plan, and normative architecture. Added Phase 4 with exact files/functions, browser-local ownership, algorithm/fallback, color layering, measurement, accessibility, licensing, and test acceptance; reconciled research and architecture docs. make format and make verify pass (1,536 pytest + 48 tryscript cases, audits and distribution checks).
