---
type: is
id: is-01m8ajqh4vp4vjajez9h4cmers
title: Port the official Lean 4 grammar (vscode-lean4 lean4.json) to a first-party Highlight.js grammar
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8ajqhjct61yx89fsjb492zs
  - type: blocks
    target: is-01m8ajqhytsk3rt4t8w8wj83vv
parent_id: is-01m8ahev7t0174z3a2vhhnpw81
hold: null
hold_until: null
created_at: 2026-11-26T00:05:19.643Z
updated_at: 2026-11-26T00:20:01.628Z
started_at: 2026-11-26T00:05:25.837Z
closed_at: 2026-11-26T00:20:01.628Z
close_reason: static/syntax/lean.js ports vscode-lean4 lean4.json rule for rule; verified in Chrome
resolution: null
duplicate_of: null
---
highlightjs-lean 1.2.0 is a Lean 3 grammar: abbrev, where, deriving, set_option, #eval, termination_by and other Lean 4 keywords render as plain text, and doc comments take the keyword color. Port leanprover/vscode-lean4's syntaxes/lean4.json (the grammar VS Code, linguist and Shiki use for Lean 4) rule by rule to static/syntax/lean.js: each upstream match/begin regex copied verbatim as String.raw, scopes mapped to standard hljs scopes, registered as 'lean' with alias 'lean4'. Only documented adaptation: definitionName's POSIX [:space:] becomes \s; the embedded Markdown grammar in comments is dropped.
