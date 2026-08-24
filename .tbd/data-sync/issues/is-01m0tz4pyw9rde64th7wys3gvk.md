---
type: is
id: is-01m0tz4pyw9rde64th7wys3gvk
title: "Step 1: Add bounded DOM-free syntax token SDK"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0dmjfnekkf22fb5zhmj1nke
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:44:30.811Z
updated_at: 2026-08-24T22:55:39.812Z
closed_at: 2026-08-24T22:55:39.811Z
close_reason: Implemented bounded, abortable mb.highlightSyntax with shared injected UTF-8 limit, terminal asset settlement, strict DOM-free token scanning, typed public contract, and focused ready/delayed/failure/entity/malformed/boundary tests; make verify passed with 1,511 tests.
resolution: null
duplicate_of: null
---
Files and interfaces: src/metabrowser/static/plugin-sdk.js functions syntaxHighlightMaxBytes, isLargeTextPreview, scanHighlightMarkup, waitForSyntaxAssets, and public highlightSyntax; src/metabrowser/static/types.d.ts interfaces MetabrowserSyntaxTokenRun, MetabrowserSyntaxTokenLines, MetabrowserSdk.highlightSyntax, and global hljs.highlight/getLanguage; tests/dom/syntax-token-sdk-behavior.js plus tests/test_plugin_sdk_behavior_js.py and tests/test_plugin_sdk_helpers.py. Behavior: read METABROWSER_SETTINGS.SYNTAX_HIGHLIGHT_MAX_BYTES with the 512 KiB package fallback; enforce UTF-8 bytes; wait for the terminal optional-assets event without hanging; call hljs.highlight(source, {language, ignoreIllegals:true}); scan only validated hljs spans and the five emitted entities into per-line data while carrying class state over newlines. Invariants: exact text round trip, no innerHTML or DOM parsing, unknown/unavailable/over-limit/lexer-or-scanner failure returns null, AbortSignal rejects AbortError, and existing regular-view enhancement still uses the same registry and loading tier. TDD acceptance: focused Node tests first fail then pass for ready, delayed, failed assets, unknown grammar, boundary sizes including multibyte text, multiline spans, all five entities, malformed tags/classes/entities, lexer throw, and abort; declarations and runtime exports stay synchronized.

## Notes

Implementation started after reviewed design head 5604e04 passed local make verify and all five GitHub checks. Applying TDD: add the focused Node SDK contract first, confirm red, then implement the token service and declarations.
