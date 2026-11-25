---
type: is
id: is-01m88dhvs3efhq2qjqr4tvrtxq
title: "PR #811 A2: an open fold is a single row to place-keeping, so a place inside it is lost or shifts"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:56:22.172Z
updated_at: 2026-11-25T05:18:21.603Z
started_at: 2026-11-25T03:59:30.667Z
closed_at: 2026-11-25T05:18:21.496Z
close_reason: "Fixed in deba14ccd: markdownRows lists blocks in page order, open folds' among them; diff-current-chrome.mjs checks view switches and paging inside an open fold. https://github.com/jlevy/metabrowser/pull/811#issuecomment-7153635595"
resolution: null
duplicate_of: null
---
Medium. diff-view.js drawnRows (3466-3484), blockAt (3524-3528); diff-markdown.js 1389-1392. drawnRows maps only rendered.children, so an open fold group is one row with no data-block; a view switch loses it and chunks inside a long open fold shift the place. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
