---
type: is
id: is-01m0dmjfnekkf22fb5zhmj1nke
title: "Step 2: Build side-specific diff syntax model"
kind: feature
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz5b6q1ewdd1e3nmn6b2qg
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-19T18:29:40.141Z
updated_at: 2026-08-25T00:07:06.651Z
closed_at: 2026-08-24T23:03:41.103Z
close_reason: Implemented strict side-specific diff syntax model in diff-syntax.js with independent old/new hunk reconstruction, path-specific language resolution, stable line records, whole-file UTF-8 measurement, exact token round-trip validation, safe plain-text fallback, and focused DOM behavior coverage. make format and make verify pass (1512 pytest, 48 golden).
resolution: null
duplicate_of: null
---
Files and functions: new strict src/metabrowser/builtin_plugins/diff/diff-syntax.js exports buildHunkRecords, syntaxInputBytes, languageForSide, highlightHunkSides, and applySideTokens; extend tests/dom/diff-syntax-behavior.js and tests/test_diff_browser_js.py. Behavior: assign stable old/new numbers to semantic line records, reconstruct context+deletion and context+addition sources independently per hunk, resolve renamed old/new paths through mb.langForExtension, check combined per-file UTF-8 input before any lexer call, and attach oldTokens/newTokens only after token line counts and per-line text round trips pass. Invariants: unified context can consume new tokens while split context retains both; no mixed patch or per-line lexing; no half-highlighted over-limit file; no wire-format mutation; hunk grammar state never crosses omitted gaps; no-newline/truncation metadata and exact source text survive. TDD acceptance: pure Node cases cover add/delete/modify, renamed extension, multiline constructs, blank/trailing lines, unknown language, over-limit combined sides, mismatch fallback, and a hunk beginning inside an omitted multiline construct whose degradation stays cosmetic and hunk-local.

## Notes

SDK dependency ca5a51f is pushed. Starting pure strict diff-syntax model with focused Node behavior coverage before renderer integration.
