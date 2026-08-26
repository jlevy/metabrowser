---
type: is
id: is-01m0xyc7gj5qhj6w8sz58qdf4m
title: Fix folder expansion after Git-panel round trip during indexing
kind: bug
status: in_progress
priority: 0
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T02:28:51.850Z
updated_at: 2026-08-26T03:14:30.069Z
---
Reproduce and fix the client-side state regression where switching to Git history while the inventory is still scanning, browsing revisions, and returning to Files leaves folder rows visible but their expand controls inert until a full reload. Inspect src/metabrowser/static/app.js navigation-panel mounting, file-tree event ownership, route/panel activation, inventory completion refresh, and any replacement/disposal state shared with git-panel.js. Add a focused failing browser contract test plus headed coverage of scanning -> Git browse -> Files -> expand. Preserve live inventory updates, one handler owner, selection/route state, and ordinary reload behavior. Acceptance: the exact sequence expands and collapses folders without reload, repeated panel round trips do not duplicate handlers, focused tests and standard file/Git headed scenarios pass, make format and make verify pass, exact global build is reinstalled, and PR #82 evidence is updated.

## Notes

Root cause: live inventory folders from _buildRowHtml used inline display:none without tree-children-collapsed. The keyboard synchronizer derived aria-expanded from the missing class, so rows returned from Git logically expanded while their child groups stayed hidden until reload. Repair: all rendered, live-inserted, and restored child groups use treeChildGroupStartHtml; the Git performance scenario now exercises the pre-index Files-to-Git-diff-to-Files round trip with trusted input and validates class, ARIA, inline style, computed visibility, and timings. Validation so far: direct cold-scan browser reproduction passes on the source candidate; 99 focused tests pass; make format passes; full make verify passes with 1,559 tests and 48 golden scenarios. Exact committed/global headed validation remains before closure.
