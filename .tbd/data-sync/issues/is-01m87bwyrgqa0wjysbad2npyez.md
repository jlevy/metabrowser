---
type: is
id: is-01m87bwyrgqa0wjysbad2npyez
title: "Pin drawnRows' tree-row branch in the Diff | Current session (review B2 on #765)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T18:08:14.090Z
updated_at: 2026-11-24T18:08:14.090Z
---
Review B on #765 (B2, suggestion): the tree-row branch of drawnRows (diff-view.js ~3299-3317), new in A3's fix, is covered by neither tests/dom/diff-current-session.js nor the Chrome check. The reviewer's scratch step on config/app.yaml's tree showed the removed $/1 row giving its place to $/2 at 20 px and context row $/4 holding at 0 px through Current and back while the bar moved 80 px. Add that step to the session and re-record cli-ui-diff-current.
