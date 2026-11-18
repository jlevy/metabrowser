---
type: is
id: is-01m7r7t20z7q6bqhvqz12szhjs
title: "Pulls nav: one outer hover/selection zone for a pull request's three lines; Space toggles its diff summary; only a click on the summary line's toggle expands it"
kind: feature
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T21:08:08.349Z
updated_at: 2026-11-18T21:09:11.985Z
started_at: 2026-11-18T21:09:11.984Z
---
Owner, 2026-11-18: In the PR view nav column, we currently make the first two lines and the third line (with the diff summary toggle) different sections for the purposes of nav and clicking. Change this so all three lines are the same hover zone by default as the outer hover zone, and then there is an inner one that expands if you click on just the diff summary line. By default we would only be doing the outer zone of all three at once, so arrow keys and the space key work as expected. Space would toggle the diff summary whenever the PR item (all 3 lines) was selected. But click would not expand by default unless you click the summary expand line, the part of the line with the toggle.

## Notes

Owner, 2026-11-18, follow-up: This is almost all the same design system. The only difference between this and the files view is that when you click a folder, it automatically toggles because you're clicking on the line with the toggle. In a way, it's still consistent. -> Build the PR item on the Files tree's row machinery: the outer item is the tree item's selection zone; the summary line is a folder-style toggle line (a click on it toggles, as on a folder line); the title and number/author lines are part of the same item and select or open without toggling.
