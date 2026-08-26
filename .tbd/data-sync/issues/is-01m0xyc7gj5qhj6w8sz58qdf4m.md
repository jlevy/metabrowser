---
type: is
id: is-01m0xyc7gj5qhj6w8sz58qdf4m
title: Fix folder expansion after Git-panel round trip during indexing
kind: bug
status: in_progress
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T02:28:51.850Z
updated_at: 2026-08-26T02:28:56.881Z
---
Reproduce and fix the client-side state regression where switching to Git history while the inventory is still scanning, browsing revisions, and returning to Files leaves folder rows visible but their expand controls inert until a full reload. Inspect src/metabrowser/static/app.js navigation-panel mounting, file-tree event ownership, route/panel activation, inventory completion refresh, and any replacement/disposal state shared with git-panel.js. Add a focused failing browser contract test plus headed coverage of scanning -> Git browse -> Files -> expand. Preserve live inventory updates, one handler owner, selection/route state, and ordinary reload behavior. Acceptance: the exact sequence expands and collapses folders without reload, repeated panel round trips do not duplicate handlers, focused tests and standard file/Git headed scenarios pass, make format and make verify pass, exact global build is reinstalled, and PR #82 evidence is updated.
