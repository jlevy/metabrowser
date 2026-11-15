---
type: is
id: is-01m7g6xxw3q44b9fp1ehr3nfq1
title: "Menus: a key that opens a menu moves keyboard focus into it"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T18:18:51.139Z
updated_at: 2026-11-15T18:18:51.139Z
---
The user's request (2026-11-15), verbatim:

"finally if we pick a menu, e.g. a filter via 1 or 2 or another key, then it should keyboard select the menu"

Done when opening a menu with its key (a toolbar number such as 1 for Group by or 2 and 3 for the drawer's filters, or any other key that opens a menu) moves keyboard focus into the menu, onto its checked row or else its first row, so the arrow keys, Enter, Escape and the menu's own keys work at once. Escape returns focus to the trigger. This applies to every menu a key opens, through one shared path in the menu controls, not per menu, and matches the existing precedent where W opens the branch list and focuses its checked row. Covered by a browserless session and a Chrome check of document.activeElement after each key. The design system states the rule.
