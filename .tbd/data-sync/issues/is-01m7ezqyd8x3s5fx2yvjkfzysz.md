---
type: is
id: is-01m7ezqyd8x3s5fx2yvjkfzysz
title: "Sans Markdown: h2 headings upright; serif documents keep the italic"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:54:00.615Z
updated_at: 2026-11-15T07:10:23.621Z
started_at: 2026-11-15T07:10:23.619Z
---
The user's request (2026-11-15), verbatim: "on the chrome or sans markdown docs let's not make the h2s italic. we can preserve the italic on the serif mode as that is more consistent with our standared past kpress stylings."

Where the italic comes from: KPress 0.3.5's `format/static/css/document.css` sets `.kpress-prose h2 { font-family: var(--kpress-font-prose, …); font-style: italic; font-weight: 400 }`. The shell sets no rule that undoes it for a sans face. KPress also sets italic on `h4` and `h6`, but the user named h2s, so those are unchanged.

Sans contexts:
- **Chrome Markdown:** anything inside `.chrome-prose` (#438: PR descriptions, comments, reviews, commit bodies).
- **Documents under the sans reading font:** `html[data-prose-font="sans"]`.
- **The `md-body` fallback** under the sans reading font, if its h2 inherits the italic.

Done when:
- an h2 in any sans context is upright (`font-style: normal`), keeping its size, weight and spacing;
- an h2 in a serif document stays italic, exactly as now;
- the rule is one scoped rule in the shell's prose styles, tied to the same face hook #438 uses (`--kpress-host-font-prose` and `.chrome-prose`) rather than to each surface, and stated once in `docs/design-system.md` next to "Serif Is for Documents";
- it's measured in headless Chrome for every context × both reading fonts × both font sets, by extending #438's `tests/dom/prose-faces-chrome.mjs` session with an h2 `font-style` check that fails before the fix;
- CHANGELOG is updated.

Depends on #438's `.chrome-prose`. Pull request 7 of the plan's stack.
