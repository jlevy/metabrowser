---
type: is
id: is-01m75z3g7adx5x5ypnxtfmwdek
title: "PR #354 A1: Pulls row titles keep breathing and aria-busy after core preparation stops"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m75z31wt2khnr26spwbyy984
hold: null
hold_until: null
created_at: 2026-11-11T18:49:40.841Z
updated_at: 2026-11-11T19:23:48.443Z
started_at: 2026-11-11T18:49:50.812Z
closed_at: 2026-11-11T19:23:48.430Z
close_reason: "fixed in bba07860: coreRefreshing requires a followed, live batch; cancelCoreRetry repaints; pinned by github-pulls-viewport-behavior titleBreathing.offline"
resolution: null
duplicate_of: null
---
Medium. pulls-panel.js coreRefreshing, cancelCoreRetry, onOffline: settle the batch and repaint when the panel stops reading GitHub; test it. Review: https://github.com/jlevy/metabrowser/pull/354#pullrequestreview-5863835475
