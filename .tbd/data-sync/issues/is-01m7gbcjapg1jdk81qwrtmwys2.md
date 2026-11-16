---
type: is
id: is-01m7gbcjapg1jdk81qwrtmwys2
title: "Navigation reveals the item: switch the nav tab, expand folders or stack, select it"
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T19:36:45.141Z
updated_at: 2026-11-16T20:03:30.945Z
started_at: 2026-11-15T19:37:35.445Z
closed_at: 2026-11-16T20:03:30.944Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"one more general UX requirement, track as another bead and handle in parallel:

when we navigate to an item, like a file or a PR, we should switch the appropriate tab and folders to expand to the relevant item. e.g. if you search for a PR, the tab should change and expand any stack if appropriate to show the PR context in the stack. same for a file."

Done when navigating to an item by any route reveals it in the nav pane: the nav switches to the item's tab, expands the folders or stack that hold the item, selects the item, and scrolls it into view. A file goes to the Files tab, a pull request to the Pulls tab, a commit to Commits if that tab lists it. The routes are:
- Quick Search;
- a link in a document, a diff, a PR page or a commit;
- the address bar or a direct URL;
- history back and forward;
- a keyboard command that opens an item.

Existing partial behavior is folded into one shared reveal path, not duplicated: the Files tree's reveal (including Group by sections), and the Pulls nav's setCurrent opening a closed stack. The rule is stated once in docs/design-system.md, with any deliberate exception given its reason. Examples of exceptions to settle: whether keyboard focus moves to the nav or stays in the main pane, and what happens when the item is filtered out of the tree, so that it is revealed with the filter noted rather than silently not found.

Covered by browserless sessions for the reveal decisions (which tab, which folders or stacks open, what is selected, for each route) against the production JavaScript, with goldens as AGENTS.md's parity rules require, and Chrome checks that the row is visible and selected after each route.
