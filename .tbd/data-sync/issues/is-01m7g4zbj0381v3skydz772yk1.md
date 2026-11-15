---
type: is
id: is-01m7g4zbj0381v3skydz772yk1
title: "Pulls toolbar: fit the default 299 px pane with the Group by stack toggle"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T17:44:40.767Z
updated_at: 2026-11-15T17:44:40.767Z
---
Found in #450's review A (finding A4) and measured by its fix (2026-11-15).

Before #450 the Pulls toolbar held the Show group (Open, Closed, All, each with its count) and Reload, with 23 px to spare at the default 299 px pane. #450 adds the Group by stack toggle, and no form of it fits: at 299 px the worded chip "Stacks" overflows by 36 px, "Stack" by 31 px, the original glyph chip by 11 px (17 px at the chip's own padding), and an `.icon-btn` by 7 px. The toolbar scrolls on its one line, so Reload is partly cut off at that width.

Options put to the user (decision pending):
- Icon-only toggles: Group by stack and Reload as icon buttons, which needs a pressed look added to the shared `.icon-btn` / `toggleHtml` icon form (docs/design-system.md, "Every Icon-Only Control Is the Same Control").
- Move Group by stack into a menu.

Done when the Pulls toolbar fits the default 299 px pane with no overflow, measured in Chrome and asserted in tests/dom/github-pulls-stacks-chrome.mjs, and the Stacks section of docs/design-system.md records the measurement.
