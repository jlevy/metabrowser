---
type: is
id: is-01m0xyc7gj5qhj6w8sz58qdf4m
title: Fix folder expansion after Git-panel round trip during indexing
kind: bug
status: closed
priority: 0
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T02:28:51.850Z
updated_at: 2026-08-26T03:38:27.319Z
closed_at: 2026-08-26T03:38:27.318Z
close_reason: Fixed and independently validated on the exact globally installed pushed head.
resolution: null
duplicate_of: null
---
Reproduce and fix the client-side state regression where switching to Git history while the inventory is still scanning, browsing revisions, and returning to Files leaves folder rows visible but their expand controls inert until a full reload. Inspect src/metabrowser/static/app.js navigation-panel mounting, file-tree event ownership, route/panel activation, inventory completion refresh, and any replacement/disposal state shared with git-panel.js. Add a focused failing browser contract test plus headed coverage of scanning -> Git browse -> Files -> expand. Preserve live inventory updates, one handler owner, selection/route state, and ordinary reload behavior. Acceptance: the exact sequence expands and collapses folders without reload, repeated panel round trips do not duplicate handlers, focused tests and standard file/Git headed scenarios pass, make format and make verify pass, exact global build is reinstalled, and PR #82 evidence is updated.

## Notes

Root cause: live inventory folders from _buildRowHtml used inline display:none without tree-children-collapsed. The keyboard synchronizer derived aria-expanded from the missing class, so rows returned from Git logically expanded while their child groups stayed hidden until reload. Fixed at exact pushed head 79c2f18: all rendered, live-inserted, and restored child groups use treeChildGroupStartHtml; the standard Git scenario now exercises the pre-index Files -> Git diff -> Files round trip with trusted input and validates class, ARIA, inline style, computed visibility, and timings. Validation: 99 focused tests; make format; make verify with 1,559 tests and 48 golden scenarios; pre-commit and pre-push; exact global wheel install and doctor; manual cold-scan reproduction at 214,549 indexed files; fresh-server headed Git scenario with Files return 29.5 ms, folder expansion 70.4 ms, zero blank frames, exact selection/route/render convergence, two-request deferred hydration, two expected aborts, zero obsolete successes, exceptions, or forced layout; independent settled Git rerun and file-views scenario also pass. Exact global build remains available at http://127.0.0.1:8755/view/.
