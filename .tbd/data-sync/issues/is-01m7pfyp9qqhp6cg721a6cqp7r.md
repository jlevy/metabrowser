---
type: is
id: is-01m7pfyp9qqhp6cg721a6cqp7r
title: "Shell: a tab click made while a folder's first view still holds its first paint is lost (the Overview paints over it); honor or queue it"
kind: bug
status: in_progress
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-18T04:51:59.926Z
updated_at: 2026-11-22T21:42:42.276Z
started_at: 2026-11-22T21:03:33.097Z
---
Found by review A of #547 (A2): in headless Chrome under CPU throttling, clicking the Treemap tab while no tab was yet active was overridden when the Overview painted; the Treemap never mounted. #547's Chrome test now waits; the shell behavior itself is untracked otherwise.

## Notes

2026-11-22: fix in PR #705 (branch claude/shell-early-tab-click, head 2b0184e27), not merged; bead left open for review. Mechanism: renderFile stages a file with its tab bar and holds the first paint for the first view's data, and the staged bar's listeners, the other views' lazy mounts, and the commit's choice of view all came after that hold, so a click on the staged tab did nothing and the commit named the render's first view. Fix: bind the bar and the mounts before the first view mounts, and commit the view the stage has in front; showPreviewTab selects on a stage of the file and, before the stage exists, records the view for the render (cleared by the next selection); a tab picked on the shown bar reaches a stage of the same file (Load more), and tab switches reach a host's own views only, which also fixes a second defect found here: a tab picked on the shown file while another file was staged left that file with an unmounted view under the wrong tab. The tab functions moved from app.js to view-composition.js (bindTabs, selectTab, setActiveView, stagedFile) to stay inside startup_script_transfer_kb: the first commit failed it in CI by 1,037 bytes, and the head is 446 under the unchanged budget. Evidence: tests/dom/view-tab-hold-session.js (seven orders; golden cli-ui-view-tab-hold.tryscript.md; tests/test_view_tab_hold_js.py; parity row shell.view-tab-hold) failed in five orders against main's app.js; tests/test_treemap_legend_hover_chrome.py now clicks the staged Treemap tab during the hold through a MutationObserver (deterministic, no throttling) and failed against main's app.js with 'the tab chosen during the hold was lost'. Open question for review: bindTabs runs before the first view renders, so a .tab-btn[data-tab] a first view draws inside its own content is no longer wired by the shell as a side effect (no built-in view does this).
