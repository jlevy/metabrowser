---
type: is
id: is-01m7g4zbj0381v3skydz772yk1
title: "Pulls toolbar: drop the Stacks toggle; group by stack always"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T17:44:40.767Z
updated_at: 2026-11-15T19:01:55.354Z
started_at: 2026-11-15T17:50:35.848Z
closed_at: 2026-11-15T19:01:55.352Z
close_reason: null
resolution: null
duplicate_of: null
---
Found in #450's review A (finding A4) and measured by its fix (2026-11-15).

Before #450 the Pulls toolbar held the Show group (Open, Closed, All, each with its count) and Reload, with 23 px to spare at the default 299 px pane. #450 adds the Group by stack toggle, and no form of it fits: at 299 px the worded chip "Stacks" overflows by 36 px, "Stack" by 31 px, the original glyph chip by 11 px (17 px at the chip's own padding), and an `.icon-btn` by 7 px. The toolbar scrolls on its one line, so Reload is partly cut off at that width.

Options put to the user (decision pending):
- Icon-only toggles: Group by stack and Reload as icon buttons, which needs a pressed look added to the shared `.icon-btn` / `toggleHtml` icon form (docs/design-system.md, "Every Icon-Only Control Is the Same Control").
- Move Group by stack into a menu.

Done when the Pulls toolbar fits the default 299 px pane with no overflow, measured in Chrome and asserted in tests/dom/github-pulls-stacks-chrome.mjs, and the Stacks section of docs/design-system.md records the measurement.

## Notes

Decision, the user (2026-11-15), verbatim: "also we can drop the "Stacks" button altogether and just keep it on always in the Pulls tab". So: remove the Group by stack toggle and its setting; the Pulls tab always groups by stack. Without the chip the toolbar has its 23 px to spare at the default 299 px pane, so the overflow ends; the Chrome test asserts no overflow at that width. Supersedes the icon-only and menu options.

Done in 6913d420f on claude/pulls-stack-groups (#450): toggle, preference, and its number removed; Reload is 4 and a pull request page's numbers start at 5. Chrome at the 299 px pane: toolbar overflow 36 px -> 0, 23 px to spare (tests/dom/github-pulls-stacks-chrome.mjs checks no overflow and spare > 0). Title room unchanged by this bead.
