---
type: is
id: is-01ky8hr11fvyfsedm2h4hjdw9k
title: "Bugbot R3-1: viewport reserve must measure the status line"
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-23T22:32:40.239Z
updated_at: 2026-07-23T22:45:15.719Z
closed_at: 2026-07-23T22:45:15.719Z
close_reason: "Viewport reserve now measures the caption height (relayout: caption -> size -> measure); live-verified pane does not scroll and caption fully visible."
---
sizeViewport reserved a fixed 64px; measure the .tm-status offsetHeight (+ margin + pane padding) at sizing time so the caption always fits without pane scroll.
