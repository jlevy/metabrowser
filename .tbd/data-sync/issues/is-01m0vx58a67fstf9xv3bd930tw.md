---
type: is
id: is-01m0vx58a67fstf9xv3bd930tw
title: "PR #76 review 76-4: guard the syntax byte fallback against drift"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - review
  - syntax-highlighting
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-25T07:29:05.861Z
updated_at: 2026-08-25T07:48:08.903Z
closed_at: 2026-08-25T07:48:08.902Z
close_reason: "Rebutted 76-4: the current exact PR head has no DEFAULT_SYNTAX_HIGHLIGHT_MAX_BYTES in plugin-sdk.js. syntaxHighlightMaxBytes() reads the server-injected METABROWSER_SETTINGS.SYNTAX_HIGHLIGHT_MAX_BYTES and safely returns 0 when settings are absent. The behavioral suite already checks exact UTF-8 at/beyond an injected value. settings.py remains the only numeric authority, so the proposed duplicate-value drift guard has no second value to compare."
resolution: null
duplicate_of: null
---
PR #76 finding 76-4 (Low), src/metabrowser/static/plugin-sdk.js DEFAULT_SYNTAX_HIGHLIGHT_MAX_BYTES and tests/test_plugin_sdk_helpers.py. Add a maintained value-level guard proving the standalone SDK fallback matches settings.SYNTAX_HIGHLIGHT_MAX_BYTES.
