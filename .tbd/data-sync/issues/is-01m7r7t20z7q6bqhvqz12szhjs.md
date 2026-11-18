---
type: is
id: is-01m7r7t20z7q6bqhvqz12szhjs
title: "Pulls nav: one outer hover/selection zone for a pull request's three lines; Space toggles its diff summary; only a click on the summary line's toggle expands it"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T21:08:08.349Z
updated_at: 2026-11-18T21:08:08.349Z
---
Owner, 2026-11-18: In the PR view nav column, we currently make the first two lines and the third line (with the diff summary toggle) different sections for the purposes of nav and clicking. Change this so all three lines are the same hover zone by default as the outer hover zone, and then there is an inner one that expands if you click on just the diff summary line. By default we would only be doing the outer zone of all three at once, so arrow keys and the space key work as expected. Space would toggle the diff summary whenever the PR item (all 3 lines) was selected. But click would not expand by default unless you click the summary expand line, the part of the line with the toggle.
