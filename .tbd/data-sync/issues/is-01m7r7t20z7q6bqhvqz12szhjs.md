---
type: is
id: is-01m7r7t20z7q6bqhvqz12szhjs
title: "Pulls nav: one outer hover/selection zone for a pull request's three lines; Space toggles its diff summary; only a click on the summary line's toggle expands it"
kind: feature
status: closed
priority: 2
version: 9
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/584
    at: 2026-11-20T17:02:09.083Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-18T21:08:08.349Z
updated_at: 2026-11-20T19:11:27.787Z
started_at: 2026-11-18T21:09:11.984Z
closed_at: 2026-11-19T00:25:21.003Z
close_reason: "Landed in #584 (db33e16d2)"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 37653cb4-a3c5-4d3c-826a-30a511416e96
    linked_at: 2026-11-20T18:01:05.428Z
---
Owner, 2026-11-18: In the PR view nav column, we currently make the first two lines and the third line (with the diff summary toggle) different sections for the purposes of nav and clicking. Change this so all three lines are the same hover zone by default as the outer hover zone, and then there is an inner one that expands if you click on just the diff summary line. By default we would only be doing the outer zone of all three at once, so arrow keys and the space key work as expected. Space would toggle the diff summary whenever the PR item (all 3 lines) was selected. But click would not expand by default unless you click the summary expand line, the part of the line with the toggle.

## Notes

Owner, 2026-11-18, follow-up: This is almost all the same design system. The only difference between this and the files view is that when you click a folder, it automatically toggles because you're clicking on the line with the toggle. In a way, it's still consistent. -> Build the PR item on the Files tree's row machinery: the outer item is the tree item's selection zone; the summary line is a folder-style toggle line; the title and number/author lines are part of the same item and select or open without toggling.
Owner, 2026-11-18, the general rule: if you click on a line with a toggle, it should toggle, but if you click on a larger element that includes a toggle, it will not toggle. -> A click anywhere on the summary line toggles; a click on the title or number/author line does not. Record the rule in docs/design-system.md.
