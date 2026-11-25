---
type: is
id: is-01m87zs6nh1dkm5w9kyfs406w5
title: "One fold design: rendered Markdown's 'N unchanged blocks' draws as the diff view's blue expand bar"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m87zs7wmwcmah3snhf1yjrnf
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-24T23:55:42.637Z
updated_at: 2026-11-25T06:02:15.193Z
started_at: 2026-11-24T23:57:46.825Z
closed_at: 2026-11-25T06:02:15.186Z
close_reason: "Merged in #811"
resolution: null
duplicate_of: null
---
User request 2026-11-24: the rendered Markdown fold (details.diff-markdown-context, "N unchanged blocks") should look and behave like the diff view expand bar for hidden context, so every collapsible chunk expands and contracts the same way with the same visual design. One shared component/style, not two look-alikes; design-system.md names it.

## Notes

PR #811. foldExpander in builtin_plugins/diff/diff-fold.js is the one fold bar; the code fold (diff-view.js) and the rendered Markdown fold (diff-markdown.js) both call it. Named once in docs/design-system.md, Fold Expanders. tests/test_diff_markdown_fold_chrome.py holds both bars compute alike at rest and hovered. mb-zz81 can reuse the factory; not implemented.
