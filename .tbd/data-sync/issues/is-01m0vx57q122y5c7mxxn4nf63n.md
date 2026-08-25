---
type: is
id: is-01m0vx57q122y5c7mxxn4nf63n
title: "PR #76 review 76-2: expose syntax fallback reasons"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - review
  - syntax-highlighting
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-25T07:29:05.248Z
updated_at: 2026-08-25T07:57:28.736Z
closed_at: 2026-08-25T07:57:28.735Z
close_reason: "Fixed 76-2: highlightSyntax now records fixed profiler labels for over_limit, no_grammar, markup_rejected, and lexer_threw with grammar and UTF-8 byte count only. Diagnostics cannot change safe plain-text fallback. Focused tests cover all reasons, malformed markup, lexer failure, bounds, unknown grammar, and the existing pinned entity vocabulary; make verify passes."
resolution: null
duplicate_of: null
---
PR #76 finding 76-2 (Medium), src/metabrowser/static/plugin-sdk.js highlightSyntax/scanHighlightMarkup and diff syntax profiler integration. Make safe plain-text fallbacks observable by reason (over_limit, no_grammar, markup_rejected, lexer_threw) without changing fallback behavior, and add focused tests including the pinned entity vocabulary.
