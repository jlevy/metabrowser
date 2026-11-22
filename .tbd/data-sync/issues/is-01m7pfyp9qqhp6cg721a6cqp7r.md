---
type: is
id: is-01m7pfyp9qqhp6cg721a6cqp7r
title: "Shell: a tab click made while a folder's first view still holds its first paint is lost (the Overview paints over it); honor or queue it"
kind: bug
status: in_progress
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-18T04:51:59.926Z
updated_at: 2026-11-22T21:34:08.788Z
started_at: 2026-11-22T21:03:33.097Z
---
Found by review A of #547 (A2): in headless Chrome under CPU throttling, clicking the Treemap tab while no tab was yet active was overridden when the Overview painted; the Treemap never mounted. #547's Chrome test now waits; the shell behavior itself is untracked otherwise.

## Notes

2026-11-22: fix in PR #705 (branch claude/shell-early-tab-click, c6cfa66ab), not merged; bead left open for review. Mechanism: renderFile stages a file with its tab bar and holds the first paint for the first view's data, and the staged bar's listeners (initTabs), the other views' lazy mounts, and the commit's choice of view all came after that hold, so a click on the staged tab did nothing and the commit named the render's first view. Fix: wire the bar and the mounts before the first view mounts, commit the view the stage has in front; showPreviewTab selects on a stage of the file and, before the stage exists, records the view for the render (cleared by the next selection); a tab picked on the shown bar reaches a stage of the same file (Load more) and tab switches are scoped to the bar's own views, which also fixes a second defect found here: a tab picked on the shown file while another file was staged left that file with an unmounted view under the wrong tab. Evidence: tests/dom/view-tab-hold-session.js (production app.js functions, seven orders; golden cli-ui-view-tab-hold.tryscript.md; tests/test_view_tab_hold_js.py; parity row shell.view-tab-hold) fails in five orders against main's app.js; tests/test_treemap_legend_hover_chrome.py now clicks the staged Treemap tab during the hold through a MutationObserver (deterministic, no throttling) and fails against main's app.js with 'the tab chosen during the hold was lost'. Open question for review: initTabs now runs before the first view renders, so a .tab-btn[data-tab] a first view draws inside its own content is no longer wired by the shell as a side effect (no built-in view does this).
