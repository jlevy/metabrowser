---
type: is
id: is-01m88dhvs3efhq2qjqr4tvrtxq
title: "PR #811 A2: an open fold is a single row to place-keeping, so a place inside it is lost or shifts"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:56:22.172Z
updated_at: 2026-11-25T03:59:30.670Z
started_at: 2026-11-25T03:59:30.667Z
---
Medium. diff-view.js drawnRows (3466-3484), blockAt (3524-3528); diff-markdown.js 1389-1392. drawnRows maps only rendered.children, so an open fold group is one row with no data-block; a view switch loses it and chunks inside a long open fold shift the place. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
