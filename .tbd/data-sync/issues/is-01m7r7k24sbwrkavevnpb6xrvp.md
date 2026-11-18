---
type: is
id: is-01m7r7k24sbwrkavevnpb6xrvp
title: "Files view: the border under the file tally stops short of the full width, unlike the other section borders"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-18T21:04:19.094Z
updated_at: 2026-11-18T21:05:53.113Z
---
Owner, 2026-11-18: in the files view, the border line below the file tally and above the files does not extend the full width; it stops a little short, unlike the other border lines between the sections. Make it consistent with the other section borders.

## Notes

Diagnosis 2026-11-18 (main 341d2c5c4, headless Chrome via the browser pane, 300 px nav pane): the Files tally (.tree-summary.nav-metadata) sits inside #tree-content, the tree's scroll container, which has scrollbar-gutter: stable (styles.css, #tree-content rule). Its box and border end at x=288 while the tab bar's and filter bar's borders end at x=299: the 11 px is the reserved classic-scrollbar gutter. A scroll container clips its content at the padding box, so no CSS on the tally can paint into the gutter. The Pulls tab's .github-pulls-status and .github-pulls-connection lines are in the same scroller and stop short the same way; only the Commits line (.git-history-summary, in the toolbar slot) spans the width. Fix: move the Files and Pulls metadata lines out of the scroller into the fixed band under each tab's toolbar, where Commits' line already is; consequence: they stay in view while the tree scrolls.
