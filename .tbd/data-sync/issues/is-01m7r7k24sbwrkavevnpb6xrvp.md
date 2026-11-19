---
type: is
id: is-01m7r7k24sbwrkavevnpb6xrvp
title: "Files view: the border under the file tally stops short of the full width, unlike the other section borders"
kind: bug
status: in_progress
priority: 2
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T21:04:19.094Z
updated_at: 2026-11-19T00:22:41.967Z
started_at: 2026-11-18T21:06:44.438Z
---
Owner, 2026-11-18: in the files view, the border line below the file tally and above the files does not extend the full width; it stops a little short, unlike the other border lines between the sections. Make it consistent with the other section borders.

## Notes

Diagnosis 2026-11-18 (main 341d2c5c4, headless Chrome via the browser pane, 300 px nav pane): the Files tally (.tree-summary.nav-metadata) sits inside #tree-content, the tree's scroll container, which has scrollbar-gutter: stable (styles.css, #tree-content rule). Its box and border end at x=288 while the tab bar's and filter bar's borders end at x=299: the 11 px is the reserved classic-scrollbar gutter. A scroll container clips its content at the padding box, so no CSS on the tally can paint into the gutter. The Pulls tab's .github-pulls-status and .github-pulls-connection lines are in the same scroller and stop short the same way; only the Commits line (.git-history-summary, in the toolbar slot) spans the width. Fix: move the Files and Pulls metadata lines out of the scroller into the fixed band under each tab's toolbar, where Commits' line already is; consequence: they stay in view while the tree scrolls.


Fix 2026-11-18: PR #573 (branch claude/nav-metadata-full-width, head 23a904979, merged with origin/main after #550). Server draws an empty .nav-metadata-band under the Files filter bar (#nav-metadata-files) and the Pulls toolbar (#nav-metadata-pulls); app.js paints the Files totals and remarks there in place (the _lastTreeSummaryHtml cache and chromeHtml summary swap are gone); pulls-panel.js mounts its status and connection lines in the band the host passes (pullsNav.metadata). Measured with tests/dom/nav-metadata-chrome.mjs at 180/300/720 px panes, window height and 220 px, overflowing and not: before, every Files and Pulls metadata rule ended 11.00 px short of the pane's right edge; after, all 0.00. The lines now stay in view while scrolling (intended, in CHANGELOG). Follow-ups in the PR: root-summary-refresh session reads the painted row; stable-totals fixture widened to '+ 10,000 ignored (1001.4 MB)' so 180 px still cuts it. Eager: app.js -44 gzip bytes (gated folder shell smaller); pulls-nav.js +97 (eager only with a Pulls tab, not gated). Coordinator owns merge and close.


Review A 2026-11-18 (4 Low): A1 fixed by one CSS rule hiding a band while its panel or the scroller leads with an alert (replaces failTree's and showFailure's JS clears); A3 fixed (band z-index 1, filter bar and toolbars 2); A4 comments fixed; A2 (rows move when a line arrives mid-scroll) recorded as accepted cost in CHANGELOG and design-system Placement: the ResizeObserver compensation measured +309 gzip bytes of app.js, against the no-added-eager-bytes brief. Dispositions posted on #573; merged main (#572, #576); head 18362f9ea. Eager now: app.js -45, pulls-nav.js +56.


2026-11-18 later: merged main through #574, #583 and #585 (changelog fragments); the entry moved to changelog.d/mb-vgx3.md and CHANGELOG.md has no diff. Head 63898a090, CI green (run 44422464735, 22 pass, 1 skipping). Eager vs main: app.js -48 gzip bytes, pulls-nav.js +56.
